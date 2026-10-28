"""Offline structured adapter and client-isolation tests."""

import base64
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "evals/model-upgrade"))
import providers  # noqa: E402


class Response:
    """Small SDK-shaped response for mocked calls."""

    def __init__(self, text: str, stop_reason: str = "end_turn") -> None:
        self.content = [SimpleNamespace(text=text)]
        self.stop_reason = stop_reason
        self.model = "claude-haiku-5-5"
        self.usage = SimpleNamespace(model_dump=lambda **kwargs: {"input_tokens": 10, "output_tokens": 5})

    def model_dump(self, **kwargs):
        return {"content": [{"text": self.content[0].text}], "model": self.model,
                "stop_reason": self.stop_reason}


def test_orientation_records_parse_failure_and_truncation() -> None:
    malformed = SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: Response("not JSON")))
    result = providers.call_orientation(malformed, image_bytes=b"exact bytes", model="claude-haiku-5-5",
                                        prompt="prompt", parameters={"max_tokens": 256})
    assert result["error_class"] == "parse_failure"
    assert result["usage"]["input_tokens"] == 10
    truncated = SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: Response("{}", "max_tokens")))
    assert providers.call_orientation(truncated, image_bytes=b"x", model="claude-haiku-5-5",
                                      prompt="prompt", parameters={"max_tokens": 256})["error_class"] == "truncated"


def test_orientation_sends_exact_bytes() -> None:
    sent = {}

    def create(**kwargs):
        sent.update(kwargs)
        return Response(json.dumps({"rotation_degrees": 180, "flip_horizontal": False,
                                    "confidence": "high", "scene_description": "Scene"}))

    result = providers.call_orientation(SimpleNamespace(messages=SimpleNamespace(create=create)),
                                        image_bytes=b"immutable jpeg bytes", model="claude-haiku-5-5",
                                        prompt="prompt", parameters={"max_tokens": 256})
    source = sent["messages"][0]["content"][0]["source"]
    assert base64.b64decode(source["data"]) == b"immutable jpeg bytes"
    assert result["parsed_output"]["rotation_degrees"] == 180


def test_glare_sends_exact_jpeg_and_preserves_decoded_output() -> None:
    sent = {}
    output = b"\x89PNG\r\n\x1a\nraw"

    def edit(**kwargs):
        sent.update(kwargs)
        return SimpleNamespace(data=[SimpleNamespace(b64_json=base64.b64encode(output).decode())],
                               usage=None, model=None,
                               model_dump=lambda **kw: {"data": [{"b64_json": "base64"}]})

    result = providers.call_glare(SimpleNamespace(images=SimpleNamespace(edit=edit)),
                                  image_bytes=b"original jpeg", model="gpt-image-2.5-flare",
                                  prompt="prompt", parameters={"size": "1024x1024", "quality": "high",
                                                               "input_fidelity": "high"})
    assert sent["image"] == ("fixture.jpg", b"original jpeg", "image/jpeg")
    assert result["output_bytes"] == output
    assert result["raw_response"]["data"][0]["b64_json"] == "[saved as raw-output.png]"


def test_clients_receive_explicit_base_urls(monkeypatch) -> None:
    import anthropic
    import openai

    seen = []
    monkeypatch.setattr(anthropic, "Anthropic", lambda **kw: seen.append(kw))
    monkeypatch.setattr(openai, "OpenAI", lambda **kw: seen.append(kw))
    monkeypatch.setenv("OPENAI_BASE_URL", "https://sentinel.invalid")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://sentinel.invalid")
    providers.make_client("anthropic", "eval-anthropic")
    providers.make_client("openai", "eval-openai")
    assert seen == [
        {"api_key": "eval-anthropic", "base_url": providers.ANTHROPIC_BASE_URL, "max_retries": 0},
        {"api_key": "eval-openai", "base_url": providers.OPENAI_BASE_URL, "max_retries": 0},
    ]
