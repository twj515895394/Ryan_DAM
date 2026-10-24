from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RootState = Literal["ok", "missing", "unavailable"]


class SettingsOut(BaseModel):
    managed_root: str
    managed_root_state: RootState


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    managed_root: str = Field(min_length=1, max_length=1024)
