"""Pydantic schemas for API request/response."""

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.services.style_engine import list_styles

AVAILABLE_WRITING_STYLES = {style["name"] for style in list_styles("writing")}
AVAILABLE_VISUAL_STYLES = {style["name"] for style in list_styles("visual")}
AVAILABLE_AUDIO_STYLES = {style["name"] for style in list_styles("audio")}
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# Auth
class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)

    @field_validator("email")
    @classmethod
    def email_valid(cls, v: str) -> str:
        v = v.strip()
        if not EMAIL_PATTERN.match(v):
            raise ValueError("邮箱格式不正确")
        return v


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)

    @field_validator("email")
    @classmethod
    def email_valid(cls, v: str) -> str:
        v = v.strip()
        if not EMAIL_PATTERN.match(v):
            raise ValueError("邮箱格式不正确")
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# Project
class ProjectCreate(BaseModel):
    title: str
    source_text: str = ""
    source_type: str = "text_split"
    direction: str = ""
    style_writing: str = "modern"
    style_visual: str = "ink_wash"
    style_audio: str = "ancient_male"

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        title = v.strip() if v else ""
        if not title:
            raise ValueError("标题不能为空")
        if len(title) > 255:
            raise ValueError("标题不能超过255个字符")
        return title

    @field_validator("source_text")
    @classmethod
    def source_text_valid(cls, v: str) -> str:
        return v.strip() if v else ""

    @field_validator("source_type")
    @classmethod
    def source_type_valid(cls, v: str) -> str:
        valid = {"text_split", "short_fiction", "play_world"}
        if v not in valid:
            raise ValueError(f"不支持的场景来源类型，可选: {', '.join(valid)}")
        return v

    @model_validator(mode="after")
    def validate_source_text_for_text_split(self):
        if self.source_type == "text_split":
            text = self.source_text.strip() if self.source_text else ""
            if not text:
                raise ValueError("文段不能为空")
            if len(text) < 80:
                raise ValueError("文段至少需要80个字符")
        return self

    @field_validator("style_writing")
    @classmethod
    def style_writing_valid(cls, v: str) -> str:
        if v not in AVAILABLE_WRITING_STYLES:
            raise ValueError("不支持的写作风格")
        return v

    @field_validator("style_visual")
    @classmethod
    def style_visual_valid(cls, v: str) -> str:
        if v not in AVAILABLE_VISUAL_STYLES:
            raise ValueError("不支持的视觉风格")
        return v

    @field_validator("style_audio")
    @classmethod
    def style_audio_valid(cls, v: str) -> str:
        if v not in AVAILABLE_AUDIO_STYLES:
            raise ValueError("不支持的音频风格")
        return v


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    status: str
    source_type: str = "text_split"
    style_writing: str
    style_visual: str
    style_audio: str
    created_at: datetime
    latest_error_msg: Optional[str] = None


class SceneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    seq: int
    title: str
    text: str
    shot_type: str
    narration: str
    edit_prompt: str
    instruction: str
    character: Optional[str] = None


class ProjectDetailResponse(ProjectResponse):
    scenes: list[SceneResponse] = Field(default_factory=list)


class ProgressResponse(BaseModel):
    status: str
    step: str
    progress: int
    error_msg: Optional[str] = None


# ── Model services (issue #3) ───────────────────────────────────────
# Either a preset_id (build from a known preset) OR explicit custom fields.

_SERVICE_GROUPS = {"overseas", "china", "aggregator", "custom"}
_SERVICE_API_FORMATS = {"openai_chat", "openai_responses", "anthropic"}


class ServiceCreate(BaseModel):
    """Create a registered model service.

    Two modes:
    - preset: pass ``preset_id`` + ``api_key`` (other fields come from the preset).
    - custom: pass ``name``/``group``/``base_url``/``api_key``/``api_format``.
    """
    preset_id: Optional[str] = None
    name: Optional[str] = None
    group: Optional[str] = None
    base_url: Optional[str] = None
    api_key: str = Field(min_length=1)
    api_format: str = "openai_chat"
    stream: bool = True
    models: list[str] = Field(default_factory=list)

    @field_validator("group")
    @classmethod
    def _valid_group(cls, v):
        if v is not None and v not in _SERVICE_GROUPS:
            raise ValueError("invalid group")
        return v

    @field_validator("api_format")
    @classmethod
    def _valid_format(cls, v):
        if v not in _SERVICE_API_FORMATS:
            raise ValueError("invalid api_format")
        return v

    @model_validator(mode="after")
    def _either_preset_or_custom(self):
        if self.preset_id:
            return self
        missing = [f for f in ("name", "group", "base_url") if not getattr(self, f)]
        if missing:
            raise ValueError(f"custom service missing fields: {missing}")
        return self


class ServiceResponse(BaseModel):
    id: int
    name: str
    group: str
    base_url: str
    api_key: str  # masked
    api_format: str
    stream: bool
    models: list[str] = Field(default_factory=list)
    config: dict = Field(default_factory=dict)
    is_preset: bool
    probed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class ServiceProbeResponse(BaseModel):
    success: bool
    api_format: str
    stream_support: bool
    models: list[str] = Field(default_factory=list)
    error: Optional[str] = None
