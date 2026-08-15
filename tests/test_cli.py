"""CLI tests: `pr1me run` end-to-end against local mock DeepSeek + ComfyUI servers."""

from __future__ import annotations

import base64
import csv
import http.server
import importlib
import json
import struct
import sys
import threading
from pathlib import Path

from pr1me.cli.main import EXIT_OK

#: A valid 1x1 PNG served by the mock ComfyUI /view endpoint.
_PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def _build_wav(sample_rate: int = 22050, seconds: float = 0.01) -> bytes:
    channels = 1
    bits = 16
    block_align = channels * bits // 8
    data_size = int(seconds * sample_rate) * block_align
    byte_rate = sample_rate * block_align
    return (
        b"RIFF"
        + struct.pack("<I", 36 + data_size)
        + b"WAVE"
        + b"fmt "
        + struct.pack("<I", 16)
        + struct.pack("<HH", 1, channels)
        + struct.pack("<II", sample_rate, byte_rate)
        + struct.pack("<HH", block_align, bits)
        + b"data"
        + struct.pack("<I", data_size)
        + bytes(data_size)
    )


_WAV = _build_wav()

#: Fake ffmpeg: emits a small valid 48 kHz mono WAV (audio mixing) on stdout,
#: or a minimal valid MP4 (ftyp + moov/mvhd) when the format is mp4 (rendering).
_FFMPEG_STUB = (
    "import struct, sys\n"
    "args = sys.argv[1:]\n"
    "def box(t, payload):\n"
    "    return struct.pack('>I', 8 + len(payload)) + t.encode() + payload\n"
    "mvhd = box('mvhd', b'\\x00\\x00\\x00\\x00' + struct.pack('>II', 0, 0)\n"
    "    + struct.pack('>II', 1000, 6000) + struct.pack('>I', 0x00010000)\n"
    "    + struct.pack('>H', 0x0100) + b'\\x00' * 10 + b'\\x00' * 36\n"
    "    + b'\\x00' * 24 + struct.pack('>I', 2))\n"
    "mp4 = box('ftyp', b'isom' + struct.pack('>I', 0x00000200) + b'isomiso2mp41') + box('moov', mvhd)\n"
    "if '-f' in args and args[args.index('-f') + 1] == 'mp4':\n"
    "    sys.stdout.buffer.write(mp4)\n"
    "    sys.stdout.buffer.flush()\n"
    "else:\n"
    "    wav = (\n"
    "        b'RIFF' + struct.pack('<I', 36 + 576000) + b'WAVE'\n"
    "        + b'fmt ' + struct.pack('<I', 16) + struct.pack('<HH', 1, 1)\n"
    "        + struct.pack('<II', 48000, 96000) + struct.pack('<HH', 2, 16)\n"
    "        + b'data' + struct.pack('<I', 576000) + bytes(576000)\n"
    "    )\n"
    "    sys.stdout.buffer.write(wav)\n"
    "    sys.stdout.buffer.flush()\n"
)
_MASTER_WAV = (
    b"RIFF"
    + struct.pack("<I", 36 + 576000)
    + b"WAVE"
    + b"fmt "
    + struct.pack("<I", 16)
    + struct.pack("<HH", 1, 1)
    + struct.pack("<II", 48000, 96000)
    + struct.pack("<HH", 2, 16)
    + b"data"
    + struct.pack("<I", 576000)
    + bytes(576000)
)

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
    "05 Thumbnail Generator": (
        '{"subject": "A clean fused first layer with perfect squish on a heated bed", '
        '"composition": "Close-up: first layer fills 70% of the frame", '
        '"colors": {"background": "deep navy", "accent": "electric orange", "text": "white"}, '
        '"curiosity_trigger": "Precision", "eye_path": "First layer to text", '
        '"text_overlay": "PERFECT SQUISH", '
        '"focal_point": "The smooth fused first layer", '
        '"concept_reason": "A clean first layer signals craft.", '
        '"style": "high-contrast technical macro render"}'
    ),
    "06 Metadata Generator": (
        '{"title": "Fix First-Layer Squish (Print Settings That Work)", '
        '"description": "Fix first-layer squish with the right print settings. '
        'Level the bed and tune the Z height, then check your first layer.", '
        '"tags": ["first layer squish", "3d printing first layer", '
        '"bed leveling 3d printer", "z offset calibration", "first layer adhesion", '
        '"print quality tips"], '
        '"hashtags": ["#FirstLayer", "#3Dprinting"], '
        '"category": "Science & Technology", "visibility": "public", "publish_at": null, '
        '"made_for_kids": false, '
        '"primary_keyword": "first layer squish", '
        '"secondary_keywords": ["bed leveling 3d printer", "first layer adhesion"], '
        '"search_intent": "How To", "target_audience": "Beginner"}'
    ),
}


class _MockDeepSeek(http.server.BaseHTTPRequestHandler):
    """Serves a canned chat-completion response on POST /chat/completions.

    The reply is picked by the marker the request's system message carries, so
    every pipeline stage receives a valid response for its own schema.
    """

    def do_POST(self) -> None:  # noqa: N802 (stdlib name)
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

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


class _MockComfyUI(http.server.BaseHTTPRequestHandler):
    """Minimal ComfyUI HTTP API: queue, history, and image retrieval."""

    def do_POST(self) -> None:  # noqa: N802 (stdlib name)
        if self.path.startswith("/prompt"):
            n = int(self.headers.get("Content-Length", 0))
            self.rfile.read(max(n, 0))
            self._respond(
                200,
                {"prompt_id": "mock-prompt-1", "number": 1, "node_errors": {}},
            )
            return
        self._respond(404, None)

    def do_GET(self) -> None:  # noqa: N802 (stdlib name)
        if self.path.startswith("/history/"):
            self._respond(
                200,
                {
                    "mock-prompt-1": {
                        "status": {"completed": True, "status_str": "success"},
                        "outputs": {
                            "9": {
                                "images": [
                                    {
                                        "filename": "pr1me_00001_.png",
                                        "subfolder": "",
                                        "type": "output",
                                    }
                                ]
                            }
                        },
                    }
                },
            )
            return
        if self.path.startswith("/view"):
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(_PNG_1X1)))
            self.end_headers()
            self.wfile.write(_PNG_1X1)
            return
        self._respond(404, None)

    def _respond(self, status: int, payload: object) -> None:
        body = json.dumps(payload).encode() if payload is not None else b""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return


class _MockVoice(http.server.BaseHTTPRequestHandler):
    """Serves a canned WAV for every POST to the voice backend endpoint."""

    def do_POST(self):  # noqa: N802 (stdlib name)
        n = int(self.headers.get("Content-Length", 0))
        self.rfile.read(max(n, 0))
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(_WAV)))
        self.end_headers()
        self.wfile.write(_WAV)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return


class _MockYouTube(http.server.BaseHTTPRequestHandler):
    """Serves the YouTube resumable upload flow: init, media, thumbnail, verify."""

    def do_POST(self) -> None:  # noqa: N802 (stdlib name)
        n = int(self.headers.get("Content-Length", 0))
        self.rfile.read(max(n, 0))
        if self.path.startswith("/upload/youtube/v3/videos"):
            body = b"{}"
            self.send_response(200)
            self.send_header("Location", f"http://127.0.0.1:{self.server.server_address[1]}/resumable/session/upload")
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path.startswith("/upload/youtube/v3/thumbnails/set"):
            self._respond(200, {"items": [{"url": "http://mock/thumb.png"}]})
            return
        self._respond(404, {"error": "unexpected youtube path"})

    def do_PUT(self) -> None:  # noqa: N802 (stdlib name)
        n = int(self.headers.get("Content-Length", 0))
        self.rfile.read(max(n, 0))
        self._respond(
            200,
            {
                "id": "mock-video-1",
                "snippet": {"title": "ignored"},
                "status": {"privacyStatus": "public", "uploadStatus": "uploaded"},
            },
        )

    def do_GET(self) -> None:  # noqa: N802 (stdlib name)
        if self.path.startswith("/youtube/v3/videos"):
            self._respond(
                200,
                {
                    "items": [
                        {
                            "id": "mock-video-1",
                            "snippet": {"publishedAt": "2026-08-07T12:00:00Z"},
                            "status": {"privacyStatus": "public", "uploadStatus": "processed"},
                        }
                    ]
                },
            )
            return
        self._respond(404, {"error": "unexpected youtube path"})

    def _respond(self, status: int, payload: object) -> None:
        body = json.dumps(payload).encode() if payload is not None else b""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return


def _start_mock(handler: type[http.server.BaseHTTPRequestHandler]) -> int:
    server = http.server.HTTPServer(("127.0.0.1", 0), handler)
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
    (prompts / "03_fact_checker.md").write_text("# 03 Fact Checker\n\nReturn a verdict.", encoding="utf-8")
    (prompts / "04_visual_director.md").write_text(
        "# 04 Visual Director\n\nReturn a shot plan.", encoding="utf-8"
    )
    (prompts / "05_thumbnail_generator.md").write_text(
        "# 05 Thumbnail Generator\n\nReturn a thumbnail concept.", encoding="utf-8"
    )
    (prompts / "06_metadata_generator.md").write_text(
        "# 06 Metadata Generator\n\nReturn publication metadata.", encoding="utf-8"
    )
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "topics.csv").write_text("topic\nLayer Height\nInfill\nSupports\n", encoding="utf-8")
    (assets / "music").mkdir()
    (assets / "music" / "bg.wav").write_bytes(_WAV)
    (assets / "sfx").mkdir()
    (assets / "sfx" / "whoosh.wav").write_bytes(_WAV)
    stub = tmp_path / "ffmpeg_stub.py"
    stub.write_text(_FFMPEG_STUB, encoding="utf-8")
    work = tmp_path / "output"
    work.mkdir()
    return {"prompts": prompts, "assets": assets, "work": work, "ffmpeg_stub": stub}


def test_run_command_writes_all_stage_artifacts(tmp_path: Path, monkeypatch) -> None:
    dirs = _workspace(tmp_path)
    port = _start_mock(_MockDeepSeek)
    comfy_port = _start_mock(_MockComfyUI)
    voice_port = _start_mock(_MockVoice)
    youtube_port = _start_mock(_MockYouTube)
    monkeypatch.setenv("PR1ME_DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("PR1ME_DEEPSEEK_BASE_URL", f"http://127.0.0.1:{port}")
    monkeypatch.setenv("PR1ME_COMFYUI_BASE_URL", f"http://127.0.0.1:{comfy_port}")
    monkeypatch.setenv("PR1ME_COMFYUI_POLL_INTERVAL", "0.01")
    monkeypatch.setenv("PR1ME_COMFYUI_MAX_RETRIES", "1")
    monkeypatch.setenv("PR1ME_VOICE_BASE_URL", f"http://127.0.0.1:{voice_port}")
    monkeypatch.setenv("PR1ME_VOICE_MAX_RETRIES", "1")
    monkeypatch.setenv("PR1ME_YOUTUBE_ACCESS_TOKEN", "ya29.test-token")
    monkeypatch.setenv("PR1ME_YOUTUBE_BASE_URL", f"http://127.0.0.1:{youtube_port}")
    monkeypatch.setenv("PR1ME_YOUTUBE_MAX_RETRIES", "1")
    monkeypatch.setenv("PR1ME_AUDIO_FFMPEG_BIN", f'"{sys.executable}" "{dirs["ffmpeg_stub"]}"')
    monkeypatch.setenv("PR1ME_AUDIO_MAX_RETRIES", "1")
    monkeypatch.setenv("PR1ME_RENDER_FFMPEG_BIN", f'"{sys.executable}" "{dirs["ffmpeg_stub"]}"')
    monkeypatch.setenv("PR1ME_RENDER_MAX_RETRIES", "1")
    monkeypatch.setenv("PR1ME_PROMPTS_DIR", str(dirs["prompts"]))
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

    visual_architecture = json.loads(
        (dirs["work"] / "visual_architecture.json").read_text(encoding="utf-8")
    )
    assert len(visual_architecture["comfyui_ready"]) == 8
    assert visual_architecture["validation"]["status"] == "ok"
    assert all(shot["score"] >= 95 for shot in visual_architecture["validation"]["prompts"])

    workflow = json.loads((dirs["work"] / "workflow.json").read_text(encoding="utf-8"))
    assert workflow["total"] == 8
    assert workflow["validation"]["status"] == "ok"
    first_frame = workflow["frames"][0]
    assert first_frame["shot_id"] == 1
    assert first_frame["block"] == "hook"
    assert first_frame["camera"] and first_frame["composition"]
    assert first_frame["motion"] and first_frame["transition"]
    assert first_frame["positive_prompt"] != first_frame["negative_prompt"]

    images_dir = dirs["work"] / "images"
    image_files = sorted(images_dir.glob("shot_*.png"))
    assert len(image_files) == 8, "expected eight rendered PNGs in output/images/"
    assert image_files[0].read_bytes().startswith(b"\x89PNG")

    manifest = json.loads((dirs["work"] / "image_manifest.json").read_text(encoding="utf-8"))
    assert manifest["total"] == 8
    assert manifest["validation"]["status"] == "ok"
    assert [image["metadata"]["shot_id"] for image in manifest["images"]] == list(range(1, 9))
    assert manifest["images"][0]["file"] == str(image_files[0])
    assert manifest["images"][0]["metadata"]["shot_id"] == 1

    audio_dir = dirs["work"] / "audio"
    audio_file = audio_dir / "narration.wav"
    assert audio_file.is_file(), "expected one narration WAV in output/audio/"

    voice = json.loads((dirs["work"] / "voice_manifest.json").read_text(encoding="utf-8"))
    assert voice["total"] == 1
    assert voice["validation"]["status"] == "ok"
    assert voice["assets"][0]["file"] == str(audio_file)
    assert voice["assets"][0]["metadata"]["sample_rate"] == 22050
    assert voice["assets"][0]["metadata"]["duration_seconds"] > 0

    audio_mix = json.loads((dirs["work"] / "audio_manifest.json").read_text(encoding="utf-8"))
    assert audio_mix["total"] == 1
    assert audio_mix["validation"]["status"] == "ok"
    asset = audio_mix["assets"][0]
    assert asset["file"] == str(dirs["work"] / "audio" / "master.wav")
    assert Path(asset["file"]).is_file()
    assert asset["metadata"]["backend"] == "ffmpeg"
    assert asset["metadata"]["bgm_file"] == str(dirs["assets"] / "music" / "bg.wav")
    assert asset["metadata"]["sfx_file"] == str(dirs["assets"] / "sfx" / "whoosh.wav")
    assert asset["metadata"]["target_lufs"] == -14
    assert Path(asset["file"]).read_bytes() == _MASTER_WAV

    motion = json.loads((dirs["work"] / "motion_graphics.json").read_text(encoding="utf-8"))
    assert motion["total_overlays"] == 1
    assert motion["validation"]["status"] == "ok"
    assert motion["overlays"][0]["text"] == "WHY DOES THE"
    assert motion["overlays"][0]["style"]["font"] == "Inter_Bold"
    assert motion["style_used"]["size_px"] == 96

    assembly = json.loads((dirs["work"] / "assembly.json").read_text(encoding="utf-8"))
    assert assembly["total_frames"] == 6 * 30
    assert assembly["fps"] == 30
    assert assembly["validation"]["status"] == "ok"
    assert assembly["tracks"]["video"][0]["file"] == str(image_files[0])
    assert assembly["tracks"]["video"][0]["end_frame"] == 27
    assert assembly["tracks"]["audio"]["file"] == str(dirs["work"] / "audio" / "master.wav")
    assert assembly["tracks"]["voice"]["file"] == str(audio_file)
    assert [entry["kind"] for entry in assembly["files"]] == ["video"] * 8 + ["voice", "audio"]

    short = dirs["work"] / "short.mp4"
    assert short.is_file(), "expected one rendered MP4 in output/"
    assert short.read_bytes()[4:8] == b"ftyp"

    render = json.loads((dirs["work"] / "render_manifest.json").read_text(encoding="utf-8"))
    assert render["file"] == str(short)
    assert render["bytes"] > 0
    assert render["validation"]["status"] == "ok"
    assert render["metadata"]["container"] == "mp4"
    assert render["metadata"]["fps"] == 30
    assert render["metadata"]["duration_seconds"] == 6.0
    assert render["metadata"]["backend"] == "ffmpeg"

    metadata = json.loads((dirs["work"] / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["title"] == "Fix First-Layer Squish (Print Settings That Work)"
    assert metadata["language"] == "en"
    assert metadata["visibility"] == "public"
    assert metadata["validation"]["status"] == "ok"
    assert 5 <= len(metadata["tags"]) <= 10

    thumbnail_png = dirs["work"] / "thumbnail.png"
    assert thumbnail_png.is_file(), "expected one rendered PNG in output/"
    assert thumbnail_png.read_bytes().startswith(b"\x89PNG")

    thumbnail = json.loads((dirs["work"] / "thumbnail_manifest.json").read_text(encoding="utf-8"))
    assert thumbnail["file"] == str(thumbnail_png)
    assert thumbnail["validation"]["status"] == "ok"
    assert thumbnail["metadata"]["backend"] == "comfyui"
    assert thumbnail["concept"]["text_overlay"] == "PERFECT SQUISH"

    publish = json.loads((dirs["work"] / "publish_manifest.json").read_text(encoding="utf-8"))
    assert publish["video_id"] == "mock-video-1"
    assert publish["url"] == "https://youtu.be/mock-video-1"
    assert publish["visibility"] == "public"
    assert publish["published_at"] == "2026-08-07T12:00:00Z"
    assert publish["dry_run"] is False
    assert publish["upload_payload"] is None
    assert publish["validation"]["status"] == "ok"


def test_run_production_pipeline_end_to_end(tmp_path: Path, monkeypatch) -> None:
    """`pr1me run --row ... --run-dir ...` runs the deterministic pipeline."""
    dirs = _workspace(tmp_path)
    voice_port = _start_mock(_MockVoice)
    monkeypatch.setenv("PR1ME_VOICE_BASE_URL", f"http://127.0.0.1:{voice_port}")
    monkeypatch.setenv("PR1ME_VOICE_MAX_RETRIES", "1")
    monkeypatch.setenv("PR1ME_RENDER_FFMPEG_BIN", f'"{sys.executable}" "{dirs["ffmpeg_stub"]}"')
    monkeypatch.setenv("PR1ME_RENDER_MAX_RETRIES", "1")
    monkeypatch.setenv("PR1ME_ASSETS_DIR", str(dirs["assets"]))
    monkeypatch.setenv("PR1ME_WORK_DIR", str(dirs["work"]))

    knowledge_csv = dirs["assets"] / "knowledge_base.csv"
    with knowledge_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["topic", "category", "subcategory", "keywords", "search_intent",
             "viewer_level", "engineering_summary", "scene_count"]
        )
        writer.writerow(
            [
                "Infill Pattern Comparisons",
                "Slicer & Print Settings",
                "Infill",
                json.dumps(["gyroid", "cubic", "grid"]),
                "what infill pattern is strongest",
                "Intermediate",
                "Gyroid is the engineering favorite.",
                "5",
            ]
        )

    run_dir = tmp_path / "run"
    monkeypatch.setattr(
        sys,
        "argv",
        ["pr1me", "run", "--row", "Infill Pattern Comparisons", "--run-dir", str(run_dir)],
    )
    cli = importlib.import_module("pr1me.cli.main")
    result = cli.main()

    assert result == EXIT_OK
    assert (run_dir / "manifest.json").is_file()
    assert (run_dir / "reports" / "execution_report.json").is_file()
    assert (run_dir / "events.json").is_file()
    assert (run_dir / "pipeline_context.json").is_file()
    for scene_id in ("S1", "S2", "S3", "S4", "S5"):
        assert (run_dir / "images" / f"{scene_id}.png").is_file()
    assert (run_dir / "audio" / "narration.wav").is_file()
    assert (run_dir / "subtitles" / "narration.srt").is_file()
    assert (run_dir / "video" / "short.mp4").is_file()
    assert (run_dir / "video" / "short.mp4").read_bytes()[4:8] == b"ftyp"
    assert (run_dir / "thumbnail" / "thumbnail.png").is_file()
    assert (run_dir / "metadata" / "metadata.json").is_file()

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "complete"
    assert manifest["topic"] == "Infill Pattern Comparisons"

    publish = json.loads((run_dir / "publish_manifest.json").read_text(encoding="utf-8"))
    assert publish["dry_run"] is True
    assert publish["video_id"].startswith("dry-run-")
