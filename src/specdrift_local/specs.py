from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from specdrift_local.models import ApiSpec, project_root


class SpecFile(BaseModel):
    apis: list[ApiSpec]


def spec_path() -> Path:
    return project_root() / "specs" / "apis.json"


def load_specs(path: Path | None = None) -> list[ApiSpec]:
    target = path or spec_path()
    with target.open("r", encoding="utf-8") as handle:
        return SpecFile.model_validate(json.load(handle)).apis
