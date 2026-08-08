"""CLI tests: `pr1me run` end-to-end against a local mock DeepSeek server."""

from __future__ import annotations

import http.server
import importlib
import json
import sys
import threading
from pathlib import Path

from pr1me.cli.main import EXIT_OK

#: Canned chat-completion replies, selected by a system-prompt marker.
_MOCK_REPLIES: dict[str, str] = {
    "01 Topic Generator": '{"topic": "First-Layer Squish: Dial It In"}',
    "02 Script Generator": (
        '{"hook": "Why does the layer lift?", "explanation": "Warping cools uneven.", '
        '"practical_insight": "Add a brim.", "ending": "Try it.", '
        '"word_count": 12}'
    ),
    "03 Fact Checker": (
        '{"verdict": "approved", "confidence": "high", "severity": "none", '
        '"findings": [], "corrections": {"hook": null, "explanation": null, '
        '"practical_insight": null, "ending": null}}'
    ),
    "04 Visual Director": (
        '{"total_seconds": 12, "shots": [{"id": 1, "block": "hook", '
        '"start_second": 0, "end_second": 6, "duration_seconds": 6, "visual": "macro", '
        '"camera": "push-in", "transition": "cut", "reason": "hook shot", '
        '"purpose": "Attention", "learning_goal": "learn the hook", '
        '"visual_type": "Macro Shot", "scene": {"subject": "bed", "environment": "bench", '
        '"composition": "centered", "lighting": "key", "camera_motion": "push", '
        '"focus": "nozzle", "style": "technical"}}], '
        '"branding": {"use_logo": true, "use_broll": true, "broll_source": null}}'
    ),
}


class _MockDeepSeek(http.server.BaseHTTPRequestHandler):
    """Serves a canned chat-completion response on POST /chat/completions.

    The reply is picked by the marker the request's system message carries, so
    every pipeline stage receives a valid response for its own schema.
    """

    def do_POST(self):  # noqa: N802 (stdlib name)
        n = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(n))
        system = ""
        for message in payload.get("messages", []):
            if message.get("role") == "system":
                system = str(message.get("content", ""))
                break
        content = '{"topic": "First-Layer Squish: Dial It In"}'
        for marker, reply in _MOCK_REPLIES.items():
            if marker in system:
                content = reply
                break
        body = json.dumps(
            {
                "choices": [{"message": {"content": content}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return


def _start_mock() -> int:
    server = http.server.HTTPServer(("127.0.0.1", 0), _MockDeepSeek)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server.server_address[1]


def _workspace(tmp_path: Path) -> dict[str, Path]:
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "01_topic_generator.md").write_text(
        "# 01 Topic Generator\n\nReturn exactly one topic.", encoding="utf-8"
    )
    (prompts / "02_script_generator.md").write_text(
        "# 02 Script Generator\n\nReturn a four-block script.", encoding="utf-8"
    )
    (prompts / "03_fact_checker.md").write_text(
        "# 03 Fact Checker\n\nReturn a verdict.", encoding="utf-8"
    )
    (prompts / "04_visual_director.md").write_text(
        "# 04 Visual Director\n\nReturn a shot plan.", encoding="utf-8"
    )
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "topics.csv").write_text(
        "topic\nLayer Height\nInfill\nSupports\n", encoding="utf-8"
    )
    work = tmp_path / "output"
    work.mkdir()
    return {"prompts": prompts, "assets": assets, "work": work}


def test_run_command_writes_all_stage_artifacts(tmp_path: Path, monkeypatch) -> None:
    dirs = _workspace(tmp_path)
    port = _start_mock()
    monkeypatch.setenv("PR1ME_DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("PR1ME_DEEPSEEK_BASE_URL", f"http://127.0.0.1:{port}")
    monkeypatch.setenv(
        "PR1ME_PROMPTS_DIR", str(dirs["prompts"])
    )
    monkeypatch.setenv("PR1ME_ASSETS_DIR", str(dirs["assets"]))
    monkeypatch.setenv("PR1ME_WORK_DIR", str(dirs["work"]))

    monkeypatch.setattr(sys, "argv", ["pr1me", "run"])
    cli = importlib.import_module("pr1me.cli.main")
    result = cli.main()

    assert result == EXIT_OK
    topic = json.loads((dirs["work"] / "topic.json").read_text(encoding="utf-8"))
    assert topic["topic"] == "First-Layer Squish: Dial It In"
    script = json.loads((dirs["work"] / "script.json").read_text(encoding="utf-8"))
    assert script["hook"] == "Why does the layer lift?"
    fact = json.loads((dirs["work"] / "fact_summary.json").read_text(encoding="utf-8"))
    assert fact["verdict"] == "approved"
    visual = json.loads((dirs["work"] / "visual_plan.json").read_text(encoding="utf-8"))
    assert visual["total_seconds"] == 12