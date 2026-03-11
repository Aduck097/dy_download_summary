import json
import tempfile

from fastapi import APIRouter, HTTPException

from web_console_backend.app.core.config import get_settings
from web_console_backend.app.schemas.config import ConfigPayload, ConfigValidationResult


router = APIRouter()


@router.get("")
def get_config() -> dict:
    settings = get_settings()
    if not settings.config_path.exists():
        raise HTTPException(status_code=404, detail="config.json not found")
    return json.loads(settings.config_path.read_text(encoding="utf-8"))


@router.put("")
def save_config(payload: ConfigPayload) -> dict[str, str]:
    settings = get_settings()
    settings.config_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload.data, ensure_ascii=False, indent=2)

    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        delete=False,
        dir=settings.config_path.parent,
        prefix=f"{settings.config_path.stem}.",
        suffix=".tmp",
    ) as handle:
        handle.write(serialized)
        temp_path = handle.name

    try:
        with open(temp_path, "r", encoding="utf-8") as test_handle:
            test_handle.read(1)
        from pathlib import Path

        Path(temp_path).replace(settings.config_path)
    except PermissionError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to write config: {exc}") from exc
    return {"status": "saved"}


@router.post("/validate", response_model=ConfigValidationResult)
def validate_config(payload: ConfigPayload) -> ConfigValidationResult:
    errors: list[str] = []
    if "paths" not in payload.data:
        errors.append("Missing required root section: paths")
    if "ffmpeg" not in payload.data:
        errors.append("Missing required root section: ffmpeg")
    return ConfigValidationResult(valid=not errors, errors=errors)
