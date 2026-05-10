"""Skills loader - discovers and indexes skills from sandbox."""

import re
from typing import Any

from sandbox.base import AbstractSandbox
from skills.models import SkillMetadata, SkillsIndex


def parse_yaml_frontmatter(content: str) -> dict[str, Any]:
    """Parse YAML frontmatter from markdown content.

    Extracts content between --- markers at the start of the file.

    Args:
        content: Full markdown file content

    Returns:
        Dictionary of frontmatter fields, or empty dict if no frontmatter
    """
    # Match frontmatter between --- markers
    pattern = r"^---\s*\n(.*?)\n---"
    match = re.match(pattern, content, re.DOTALL)
    if not match:
        return {}

    frontmatter_text = match.group(1)
    result: dict[str, Any] = {}

    # Simple YAML parsing (handles basic key: value and key: [list])
    for line in frontmatter_text.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # Match key: value
        kv_match = re.match(r"^(\w+):\s*(.*)$", line)
        if not kv_match:
            continue

        key = kv_match.group(1)
        value = kv_match.group(2).strip()

        # Handle list syntax [item1, item2]
        if value.startswith("[") and value.endswith("]"):
            # Parse as list
            list_content = value[1:-1]
            items = [item.strip().strip("'\"") for item in list_content.split(",")]
            result[key] = [item for item in items if item]
        else:
            # Strip quotes if present
            if (value.startswith('"') and value.endswith('"')) or (
                value.startswith("'") and value.endswith("'")
            ):
                value = value[1:-1]
            result[key] = value

    return result


class SkillsLoader:
    """Loads and indexes skills from sandbox directories.

    Skills are discovered by:
    1. Listing directories in each skills_path
    2. Reading SKILL.md frontmatter from each directory
    3. Building a SkillsIndex with metadata

    Only metadata (name, description, tags, entry) is loaded.
    Full SKILL.md content is read on-demand by the LLM via exec_command.
    """

    def __init__(
        self,
        skills_paths: list[str],
        sandbox: AbstractSandbox,
    ):
        """Initialize skills loader.

        Args:
            skills_paths: List of paths to scan for skills (inside sandbox)
            sandbox: Connected sandbox instance
        """
        self.skills_paths = skills_paths
        self.sandbox = sandbox

    async def load(self) -> SkillsIndex:
        """Load and index all skills from configured paths.

        Returns:
            SkillsIndex with all discovered skills
        """
        skills: list[SkillMetadata] = []
        scanned_roots: list[str] = []

        for skills_path in self.skills_paths:
            # List directories in skills_path
            folders = await self._list_skill_folders(skills_path)
            if folders:
                scanned_roots.append(skills_path)

            for folder in folders:
                skill_path = f"{skills_path}/{folder}"
                metadata = await self._load_skill_metadata(folder, skill_path)
                if metadata:
                    skills.append(metadata)

        return SkillsIndex(roots=scanned_roots, skills=skills)

    async def _list_skill_folders(self, path: str) -> list[str]:
        """List subdirectories in a path.

        Args:
            path: Path to list (inside sandbox)

        Returns:
            List of folder names, or empty list if path doesn't exist
        """
        try:
            # Use ls -1 to list one item per line, -d */ to list only directories
            result = await self.sandbox.exec(
                f"ls -1d {path}/*/ 2>/dev/null | xargs -n1 basename 2>/dev/null || true"
            )
            if result.exit_code != 0 or not result.stdout.strip():
                return []

            folders = [
                line.strip()
                for line in result.stdout.strip().split("\n")
                if line.strip()
            ]
            return folders
        except Exception:
            # Path doesn't exist or other error - skip silently
            return []

    async def _load_skill_metadata(
        self, folder: str, skill_path: str
    ) -> SkillMetadata | None:
        """Load metadata from a skill's SKILL.md file.

        Args:
            folder: Folder name (e.g., "web-scraper")
            skill_path: Full path to skill folder

        Returns:
            SkillMetadata if SKILL.md exists and is valid, None otherwise
        """
        skill_md_path = f"{skill_path}/SKILL.md"

        try:
            content_bytes = await self.sandbox.read_file(skill_md_path)
            content = content_bytes.decode("utf-8", errors="replace")
        except Exception:
            # SKILL.md doesn't exist - skip this folder
            return None

        # Parse frontmatter
        frontmatter = parse_yaml_frontmatter(content)

        # Build metadata
        return SkillMetadata(
            folder=folder,
            path=skill_path,
            name=frontmatter.get("name", folder),  # Default to folder name
            description=frontmatter.get("description", ""),
            version=frontmatter.get("version", ""),
            tags=frontmatter.get("tags", []),
            entry=frontmatter.get("entry", ""),
        )
