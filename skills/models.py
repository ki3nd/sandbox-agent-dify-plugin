"""Data models for skills."""

from dataclasses import dataclass, field


@dataclass
class SkillMetadata:
    """Metadata extracted from SKILL.md frontmatter."""

    folder: str  # Folder name (e.g., "web-scraper")
    path: str  # Full path to skill folder (e.g., "/workspace/.skills/web-scraper")
    name: str  # Display name (defaults to folder name)
    description: str = ""  # One-line summary
    version: str = ""  # Informational version
    tags: list[str] = field(default_factory=list)  # Tags for categorization
    entry: str = ""  # Entry point file (e.g., "scrape.py")

    def to_prompt_line(self, index: int) -> str:
        """Format skill for system prompt.

        Args:
            index: 1-based index for numbering

        Returns:
            Formatted string like:
            1. **Web Scraper** [web, scraping]: Scrape web pages
               Path: `/workspace/.skills/web-scraper` | Entry: `scrape.py`
        """
        tags_str = f" [{', '.join(self.tags)}]" if self.tags else ""

        line = f"{index}. **{self.name}**{tags_str}"
        if self.description:
            line += f": {self.description}"

        details = [f"`{self.path}`"]
        if self.entry:
            details.append(f"Entry: `{self.entry}`")
        line += f"\n   Path: {' | '.join(details)}"

        return line


@dataclass
class SkillsIndex:
    """Index of all discovered skills."""

    roots: list[str]  # Paths that were scanned
    skills: list[SkillMetadata] = field(default_factory=list)

    def is_empty(self) -> bool:
        """Return True if no skills were found."""
        return len(self.skills) == 0

    def to_prompt_context(self) -> str:
        """Generate prompt context for system prompt injection.

        Returns:
            Formatted string with all skills listed, or empty string if no skills.
        """
        if self.is_empty():
            return ""

        lines = [
            "## Available Agent Skills",
            "",
            "A skill is a set of local instructions stored in a `SKILL.md` file. "
            "Each entry below includes name, description, and path — use `exec_command` "
            "to open the source for full instructions when using a specific skill.",
            "",
        ]

        for i, skill in enumerate(self.skills, start=1):
            lines.append(skill.to_prompt_line(i))

        lines += [
            "",
            "### How to use skills",
            "",
            "- **Trigger**: Use a skill when the user names it or when the task clearly "
            "matches a skill's description above. Multiple matches → use all applicable skills.",
            "- **Progressive disclosure**:",
            "  1. Run `cat {skill_path}/SKILL.md` to read the skill instructions.",
            "  2. Only load extra files (`references/`, `scripts/`) when directly needed.",
            "  3. If `scripts/` exist, prefer running them over retyping code blocks.",
            "- **Multi-skill**: If multiple skills apply, state which ones and the order "
            "you'll use them (one short line).",
            "- **Context hygiene**: Summarize long `SKILL.md` sections instead of pasting "
            "them verbatim. Avoid bulk-loading all files in a skill directory.",
            "- **Fallback**: If a skill can't be applied (missing files, unclear instructions), "
            "say so briefly and continue with the best available approach.",
        ]

        return "\n".join(lines)
