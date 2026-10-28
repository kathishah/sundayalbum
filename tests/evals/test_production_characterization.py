"""Pin production fallback, retry classification, and confidence gating."""

from types import SimpleNamespace

import numpy as np
from src.ai import claude_vision
from src.glare import remover_openai


def test_orientation_api_error_passes_through(monkeypatch) -> None:
    class BrokenAnthropic:
        def __init__(self, **kwargs):
            pass

        messages = SimpleNamespace(
            create=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("offline"))
        )

    monkeypatch.setattr(claude_vision, "Anthropic", BrokenAnthropic)
    image = np.zeros((4, 6, 3), dtype=np.float32)
    result = claude_vision.analyze_photo_for_processing(image, api_key="test-only")
    assert result.rotation_degrees == 0
    assert result.orientation_confidence == "low"
    assert result.scene_description == ""


def test_low_confidence_disables_rotation_and_flip() -> None:
    image = np.arange(72, dtype=np.float32).reshape(4, 6, 3)
    analysis = claude_vision.PhotoAnalysis(180, True, "low", "scene")
    assert claude_vision.apply_orientation(image, analysis) is image


def test_openai_error_classification(monkeypatch) -> None:
    class ApiError(Exception):
        pass

    class RateLimitError(ApiError):
        pass

    class AuthError(ApiError):
        pass

    class ServerError(ApiError):
        pass

    fake = SimpleNamespace(
        RateLimitError=RateLimitError,
        InternalServerError=ServerError,
        APIConnectionError=ServerError,
        APITimeoutError=ServerError,
        AuthenticationError=AuthError,
        PermissionDeniedError=AuthError,
        BadRequestError=AuthError,
        NotFoundError=AuthError,
        OpenAIError=ApiError,
    )
    monkeypatch.setitem(__import__("sys").modules, "openai", fake)
    assert remover_openai._classify_openai_error(RateLimitError("x")) == (5, 10)
    assert remover_openai._classify_openai_error(AuthError("x")) is None
    assert remover_openai._classify_openai_error(ServerError("x")) is not None
