#!/usr/bin/env python3
"""Helpers for loading the shared project configuration."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def load_json(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_shared_config(path: Path | None) -> dict[str, Any]:
    return load_json(path)


def get_section(config: dict[str, Any], name: str) -> dict[str, Any]:
    section = config.get(name)
    if isinstance(section, dict):
        return dict(section)
    return {}


def resolve_secret(explicit: str | None, section: dict[str, Any], *env_names: str) -> str:
    if explicit:
        return explicit
    for key in ("api_key", "access_key_id", "access_key_secret", "security_token"):
        value = section.get(key)
        if isinstance(value, str) and value:
            return value
    for env_name in env_names:
        value = os.getenv(env_name)
        if value:
            return value
    return ""
