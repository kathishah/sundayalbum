"""Explicitly credentialed, single-attempt model-stage provider adapters."""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Any

ANTHROPIC_BASE_URL = "https://api.anthropic.com"
OPENAI_BASE_URL = "https://api.openai.com/v1"


def read_eval_keys(path: Path, providers: set[str]) -> dict[str, str]:
    """Read only selected keys from a local file; never use env fallbacks."""
    if not path.is_file():
        raise FileNotFoundError(f"Eval credential file is missing: {path}")
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError("Eval credential file must contain a JSON object")
    fields = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}
    keys: dict[str, str] = {}
    for provider in providers:
        if provider not in fields:
            raise ValueError(f"Unsupported provider: {provider}")
        value = data.get(fields[provider])
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Missing {fields[provider]} in local eval credential file")
        keys[provider] = value.strip()
    return keys


def make_client(provider: str, key: str) -> Any:
    """Create a client with an explicit key, URL, and no hidden SDK retries."""
    if not key:
        raise ValueError("An explicit provider key is required")
    if provider == "anthropic":
        from anthropic import Anthropic

        return Anthropic(api_key=key, base_url=ANTHROPIC_BASE_URL, max_retries=0)
    if provider == "openai":
        from openai import OpenAI

        return OpenAI(api_key=key, base_url=OPENAI_BASE_URL, max_retries=0)
    raise ValueError(f"Unsupported provider: {provider}")


def preflight(client: Any, model: str) -> None:
    """Make a cheap authenticated model lookup before the first paid request."""
    client.models.retrieve(model)


def _usage(response: Any) -> dict | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    return usage.model_dump(mode="json") if hasattr(usage, "model_dump") else dict(usage)


def _raw(response: Any) -> dict:
    return response.model_dump(mode="json") if hasattr(response, "model_dump") else dict(response)


def _error(exc: Exception, latency_ms: int) -> dict:
    name = type(exc).__name__
    status_code = getattr(exc, "status_code", None)
    retryable = status_code in (408, 409, 429) or (
        isinstance(status_code, int) and status_code >= 500
    )
    if status_code is None and name in {"APIConnectionError", "APITimeoutError"}:
        retryable = True
    return {
        "status": "failed",
        "error_class": "provider_error",
        "error_type": name,
        "http_status": status_code,
        "retryable": retryable,
        "error": str(exc)[:300],
        "latency_ms": latency_ms,
        "raw_response": None,
        "parsed_output": None,
        "usage": None,
    }


def parse_orientation(text: str) -> dict:
    """Parse strict structured orientation output; reject invalid fields."""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            stripped = "\n".join(lines[1:-1]).strip()
    value = json.loads(stripped)
    if not isinstance(value, dict):
        raise ValueError("Orientation output must be a JSON object")
    rotation = value.get("rotation_degrees")
    if type(rotation) is not int or rotation not in (0, 90, 180, 270):
        raise ValueError("Invalid rotation_degrees")
    if type(value.get("flip_horizontal")) is not bool:
        raise ValueError("Invalid flip_horizontal")
    if value.get("confidence") not in ("low", "medium", "high"):
        raise ValueError("Invalid confidence")
    if not isinstance(value.get("scene_description"), str):
        raise ValueError("Invalid scene_description")
    return value


def call_orientation(
    client: Any, *, image_bytes: bytes, model: str, prompt: str, parameters: dict
) -> dict:
    """Send one exact JPEG fixture to Anthropic and capture a structured result."""
    start = time.monotonic()
    try:
        response = client.messages.create(
            model=model,
            **parameters,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": base64.b64encode(image_bytes).decode("ascii"),
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
        latency_ms = round((time.monotonic() - start) * 1000)
        raw = _raw(response)
        common = {
            "raw_response": raw,
            "usage": _usage(response),
            "resolved_model": getattr(response, "model", None),
            "latency_ms": latency_ms,
            "stop_reason": getattr(response, "stop_reason", None),
        }
        if common["stop_reason"] == "max_tokens":
            return {
                "status": "failed",
                "error_class": "truncated",
                "retryable": False,
                "parsed_output": None,
                **common,
            }
        try:
            text_blocks = [
                block.text
                for block in response.content
                if getattr(block, "type", "text") == "text" and hasattr(block, "text")
            ]
            if not text_blocks:
                raise ValueError("No text content block in orientation response")
            parsed = parse_orientation("\n".join(text_blocks))
        except (IndexError, AttributeError, ValueError, json.JSONDecodeError) as exc:
            return {
                "status": "failed",
                "error_class": "parse_failure",
                "error": str(exc),
                "retryable": False,
                "parsed_output": None,
                **common,
            }
        return {"status": "success", "parsed_output": parsed, "retryable": False, **common}
    except Exception as exc:
        return _error(exc, round((time.monotonic() - start) * 1000))


def call_glare(
    client: Any, *, image_bytes: bytes, model: str, prompt: str, parameters: dict
) -> dict:
    """Send one exact JPEG fixture to OpenAI images.edit and capture its PNG."""
    start = time.monotonic()
    try:
        request = dict(
            model=model,
            image=("fixture.jpg", image_bytes, "image/jpeg"),
            prompt=prompt,
            n=parameters.get("n", 1),
            size=parameters["size"],
            quality=parameters["quality"],
            output_format="png",
        )
        if parameters.get("input_fidelity") is not None:
            request["input_fidelity"] = parameters["input_fidelity"]
        response = client.images.edit(**request)
        latency_ms = round((time.monotonic() - start) * 1000)
        raw = _raw(response)
        output_b64 = response.data[0].b64_json
        if not output_b64:
            return {
                "status": "failed",
                "error_class": "missing_image",
                "retryable": False,
                "raw_response": {**raw, "data": "[omitted]"},
                "usage": _usage(response),
                "parsed_output": None,
                "latency_ms": latency_ms,
            }
        output = base64.b64decode(output_b64, validate=True)
        # Store the provider's decoded PNG unchanged; omit duplicated base64 from JSON.
        raw["data"] = [{"b64_json": "[saved as raw-output.png]"}]
        return {
            "status": "success",
            "raw_response": raw,
            "usage": _usage(response),
            "resolved_model": getattr(response, "model", None),
            "parsed_output": {"output_sha256": __import__("hashlib").sha256(output).hexdigest()},
            "output_bytes": output,
            "latency_ms": latency_ms,
            "retryable": False,
        }
    except Exception as exc:
        return _error(exc, round((time.monotonic() - start) * 1000))
