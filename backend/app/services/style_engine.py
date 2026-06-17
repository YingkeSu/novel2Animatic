"""Style plugin engine - loads and applies YAML style configs."""

import yaml
from pathlib import Path
from typing import Any

STYLES_DIR = Path(__file__).parent.parent.parent / "styles"


def load_style(style_type: str, style_name: str) -> dict[str, Any]:
    """Load a style plugin YAML by type and name."""
    style_file = STYLES_DIR / style_type / f"{style_name}.yaml"
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
    styles_dir = STYLES_DIR / style_type
    if not styles_dir.exists():
        return []
    result = []
    for f in sorted(styles_dir.glob("*.yaml")):
        with open(f, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        result.append({"name": f.stem, "display": data.get("name", f.stem), "description": data.get("description", "")})
    return result
