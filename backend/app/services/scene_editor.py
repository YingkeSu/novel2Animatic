"""Scene editor — edit and regenerate individual scenes.

Provides validation and API for editing scene fields (text, title, narration,
edit_prompt, shot_type) and regenerating scene assets (image, audio) independently.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, List


@dataclass
class EditResult:
    """Result of a scene edit or regeneration."""
    scene_seq: int
    field: str
    old_value: Any
    new_value: Any
    success: bool
    error: str = ""


class SceneEditor:
    """Scene editing and regeneration logic.

    Usage:
        editor = SceneEditor()
        editor.validate_field("text")  # OK
        editor.validate_field("foo")   # raises ValueError
    """

    EDITABLE_FIELDS = frozenset({"text", "title", "narration", "edit_prompt", "shot_type", "instruction", "character"})
    REGENERABLE_ASSETS = frozenset({"image", "audio"})

    @property
    def editable_fields(self) -> frozenset:
        """Return the set of editable scene fields."""
        return self.EDITABLE_FIELDS

    @property
    def regenerable_assets(self) -> frozenset:
        """Return the set of regenerable asset types."""
        return self.REGENERABLE_ASSETS

    def validate_field(self, field: str) -> None:
        """Validate that a field is editable.

        Args:
            field: Field name to validate.

        Raises:
            ValueError: If field is not in editable_fields.
        """
        if field not in self.EDITABLE_FIELDS:
            raise ValueError(
                f"Field '{field}' is not editable. "
                f"Editable fields: {sorted(self.EDITABLE_FIELDS)}"
            )

    def validate_asset_type(self, asset_type: str) -> None:
        """Validate that an asset type is regenerable.

        Args:
            asset_type: Asset type to validate.

        Raises:
            ValueError: If asset_type is not in regenerable_assets.
        """
        if asset_type not in self.REGENERABLE_ASSETS:
            raise ValueError(
                f"Asset type '{asset_type}' is not regenerable. "
                f"Regenerable types: {sorted(self.REGENERABLE_ASSETS)}"
            )
