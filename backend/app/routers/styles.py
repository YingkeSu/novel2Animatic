"""Styles router."""

from fastapi import APIRouter
from app.services.style_engine import list_styles

router = APIRouter(prefix="/api/styles", tags=["styles"])


@router.get("")
async def get_styles(type: str = "writing"):
    return list_styles(type)
