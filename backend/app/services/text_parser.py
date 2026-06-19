"""=== TAG === structured text parser.

Parses LLM output formatted with === TAG_NAME === delimiters,
with fallback to Markdown ## headers. Designed for robustness
against imperfect LLM output (InkOS-inspired design).

Usage:
    from app.services.text_parser import parse_tag_blocks

    text = '''=== TITLE ===
    My Story

    === CHAPTER 1 ===
    Once upon a time...'''

    result = parse_tag_blocks(text)
    # {"TITLE": "My Story", "CHAPTER 1": "Once upon a time..."}
"""

import re
import logging
from typing import Dict

logger = logging.getLogger(__name__)


class TagParseError(Exception):
    """Raised when tag parsing encounters an unrecoverable error."""
    pass


# Pattern for === TAG_NAME === format
_TAG_PATTERN = re.compile(r"^===\s*(.+?)\s*===$", re.MULTILINE)

# Pattern for ## TAG_NAME fallback (Markdown headers)
_MD_HEADER_PATTERN = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def parse_tag_blocks(text: str) -> Dict[str, str]:
    """Parse === TAG === delimited content blocks from text.

    Extracts content between === TAG_NAME === delimiters. Falls back
    to Markdown ## headers if no === TAG === patterns found.

    Args:
        text: Raw text containing TAG-delimited blocks.

    Returns:
        Dict mapping tag names to their content strings.
        Empty dict for empty/invalid input.
        Duplicate tags: last wins.
    """
    if not text or not text.strip():
        return {}

    # Try === TAG === format first
    result = _parse_with_pattern(text, _TAG_PATTERN)

    if result:
        return result

    # Fallback to Markdown ## headers
    result = _parse_with_pattern(text, _MD_HEADER_PATTERN)
    return result


def _parse_with_pattern(text: str, pattern: re.Pattern) -> Dict[str, str]:
    """Parse text using the given regex pattern as delimiter.

    Args:
        text: Input text.
        pattern: Compiled regex pattern for tag/header delimiters.

    Returns:
        Dict mapping tag names to content.
    """
    matches = list(pattern.finditer(text))

    if not matches:
        return {}

    result: Dict[str, str] = {}

    for i, match in enumerate(matches):
        tag_name = match.group(1).strip()

        if not tag_name:
            logger.warning("Empty tag name at position %d, skipping", match.start())
            continue

        # Content starts after the tag line, ends at next tag or EOF
        content_start = match.end()
        if i + 1 < len(matches):
            content_end = matches[i + 1].start()
        else:
            content_end = len(text)

        content = text[content_start:content_end]

        # Strip leading newline but preserve internal formatting
        if content.startswith("\n"):
            content = content[1:]

        # Strip trailing whitespace
        content = content.rstrip()

        result[tag_name] = content

    return result
