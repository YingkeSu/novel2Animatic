"""Style plugin engine - loads and applies YAML style configs."""

import yaml
from pathlib import Path
from typing import Any

STYLES_DIR = Path(__file__).parent.parent.parent / "styles"


def _is_safe_component(value: str) -> bool:
    """Reject path traversal and multi-part path inputs."""
    if value in {"", ".", ".."}:
        return False
    return Path(value).name == value and Path(value).parts == (value,)


def _style_file_path(style_type: str, style_name: str) -> Path | None:
    if not _is_safe_component(style_type) or not _is_safe_component(style_name):
        return None

    styles_root = STYLES_DIR.resolve(strict=False)
    style_file = (STYLES_DIR / style_type / f"{style_name}.yaml").resolve(strict=False)
    if style_file == styles_root or styles_root not in style_file.parents:
        return None
    return style_file


def load_style(style_type: str, style_name: str) -> dict[str, Any]:
    """Load a style plugin YAML by type and name."""
    style_file = _style_file_path(style_type, style_name)
    if style_file is None:
        return {}
    if not style_file.exists():
        return {}
    with open(style_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_writing_prompt(style_name: str) -> str:
    """Get system prompt for writing style."""
    style = load_style("writing", style_name)
    return style.get("system_prompt", "")


def get_visual_suffix(style_name: str) -> str:
    """Get prompt suffix for visual style."""
    style = load_style("visual", style_name)
    return style.get("prompt_suffix", "")


def get_audio_params(style_name: str) -> dict[str, Any]:
    """Get TTS parameters for audio style."""
    style = load_style("audio", style_name)
    return {
        "voice": style.get("voice", "cixingnansheng"),
        "instruction": style.get("default_instruction", ""),
        "speed": style.get("speed", 1.0),
        "volume": style.get("volume", 1.0),
    }


def list_styles(style_type: str) -> list[dict[str, str]]:
    """List available styles of a given type."""
    if not _is_safe_component(style_type):
        return []

    styles_dir = STYLES_DIR / style_type
    if not styles_dir.exists():
        return []
    result = []
    for f in sorted(styles_dir.glob("*.yaml")):
        with open(f, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        result.append({"name": f.stem, "display": data.get("name", f.stem), "description": data.get("description", "")})
    return result
