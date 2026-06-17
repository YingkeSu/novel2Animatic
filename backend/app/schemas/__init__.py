"""Pydantic schemas for API request/response."""

from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import datetime
from typing import Optional


# Auth
class RegisterRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# Project
class ProjectCreate(BaseModel):
    title: str
    source_text: str
    style_writing: str = "modern"
    style_visual: str = "ink_wash"
    style_audio: str = "ancient_male"

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("标题不能为空")
        return v.strip()

    @field_validator("source_text")
    @classmethod
    def source_text_valid(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("文段不能为空")
        if len(v.strip()) < 5:
            raise ValueError("文段至少需要5个字符")
        return v.strip()


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    status: str
    style_writing: str
    style_visual: str
    style_audio: str
    created_at: datetime


class SceneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    seq: int
    title: str
    text: str
    shot_type: str
    narration: str
    character: Optional[str] = None


class ProjectDetailResponse(ProjectResponse):
    scenes: list[SceneResponse] = Field(default_factory=list)


class ProgressResponse(BaseModel):
    status: str
    step: str
    progress: int
    error_msg: Optional[str] = None
