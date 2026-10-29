"""Repository-root path selection for local pipeline secrets."""

from pathlib import Path

from src.utils import secrets as secrets_module


def test_default_secrets_file_is_at_repository_root() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    assert secrets_module._SECRETS_FILE == repository_root / "secrets.json"
