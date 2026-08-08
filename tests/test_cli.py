"""CLI tests: `pr1me run` end-to-end against a local mock DeepSeek server."""

from __future__ import annotations

import http.server
import importlib
import json
import sys
import threading
from pathlib import Path

from pr1me.cli.main import EXIT_OK


class _MockDeepSeek(http.server.BaseHTTPRequestHandler):
    """Serves a canned chat-completion response on POST /chat/completions."""

    def do_POST(self):  # noqa: N802 (stdlib name)
        n = int(self.headers.get("Content-Length", 0))
        self.rfile.read(n)
        body = json.dumps(
            {
                "choices": [
                    {"message": {"content": '{"topic": "First-Layer Squish: Dial It In"}'}}
                ],
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
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "topics.csv").write_text(
        "topic\nLayer Height\nInfill\nSupports\n", encoding="utf-8"
    )
    work = tmp_path / "output"
    work.mkdir()
    return {"prompts": prompts, "assets": assets, "work": work}


def test_run_command_writes_topic_json(tmp_path: Path, monkeypatch) -> None:
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
    artifact = json.loads((dirs["work"] / "topic.json").read_text(encoding="utf-8"))
    assert artifact["topic"] == "First-Layer Squish: Dial It In"