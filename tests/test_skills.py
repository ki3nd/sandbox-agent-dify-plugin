"""Tests for skills loading."""

import pytest
from skills.models import SkillMetadata, SkillsIndex
from skills.loader import parse_yaml_frontmatter


class TestParseYamlFrontmatter:
    """Tests for YAML frontmatter parsing."""

    def test_basic_frontmatter(self):
        content = """---
name: Web Scraper
description: Scrape web pages
version: 1.0.0
---

# Web Scraper

Usage instructions here.
"""
        result = parse_yaml_frontmatter(content)
        assert result["name"] == "Web Scraper"
        assert result["description"] == "Scrape web pages"
        assert result["version"] == "1.0.0"

    def test_frontmatter_with_tags_list(self):
        content = """---
name: Data Analyzer
tags: [data, pandas, csv]
---
"""
        result = parse_yaml_frontmatter(content)
        assert result["name"] == "Data Analyzer"
        assert result["tags"] == ["data", "pandas", "csv"]

    def test_frontmatter_with_quoted_values(self):
        content = """---
name: "My Skill"
description: 'A description with: colon'
---
"""
        result = parse_yaml_frontmatter(content)
        assert result["name"] == "My Skill"
        assert result["description"] == "A description with: colon"

    def test_no_frontmatter(self):
        content = """# Just a markdown file

No frontmatter here.
"""
        result = parse_yaml_frontmatter(content)
        assert result == {}

    def test_empty_content(self):
        result = parse_yaml_frontmatter("")
        assert result == {}


class TestSkillMetadata:
    """Tests for SkillMetadata."""

    def test_to_prompt_line_basic(self):
        skill = SkillMetadata(
            folder="web-scraper",
            path="/workspace/.skills/web-scraper",
            name="Web Scraper",
            description="Scrape web pages",
        )
        line = skill.to_prompt_line(1)
        assert "1. **Web Scraper**" in line
        assert "Scrape web pages" in line
        assert "/workspace/.skills/web-scraper" in line

    def test_to_prompt_line_with_tags(self):
        skill = SkillMetadata(
            folder="web-scraper",
            path="/workspace/.skills/web-scraper",
            name="Web Scraper",
            description="Scrape web pages",
            tags=["web", "scraping"],
        )
        line = skill.to_prompt_line(1)
        assert "[web, scraping]" in line

    def test_to_prompt_line_with_entry(self):
        skill = SkillMetadata(
            folder="web-scraper",
            path="/workspace/.skills/web-scraper",
            name="Web Scraper",
            description="Scrape web pages",
            entry="scrape.py",
        )
        line = skill.to_prompt_line(1)
        assert "Entry: `scrape.py`" in line


class TestSkillsIndex:
    """Tests for SkillsIndex."""

    def test_is_empty_true(self):
        index = SkillsIndex(roots=["/workspace/.skills"], skills=[])
        assert index.is_empty() is True

    def test_is_empty_false(self):
        skill = SkillMetadata(
            folder="test",
            path="/workspace/.skills/test",
            name="Test",
        )
        index = SkillsIndex(roots=["/workspace/.skills"], skills=[skill])
        assert index.is_empty() is False

    def test_to_prompt_context_empty(self):
        index = SkillsIndex(roots=[], skills=[])
        assert index.to_prompt_context() == ""

    def test_to_prompt_context_with_skills(self):
        skills = [
            SkillMetadata(
                folder="web-scraper",
                path="/workspace/.skills/web-scraper",
                name="Web Scraper",
                description="Scrape web pages",
                tags=["web"],
                entry="scrape.py",
            ),
            SkillMetadata(
                folder="data-analyzer",
                path="/workspace/.skills/data-analyzer",
                name="Data Analyzer",
                description="Analyze data",
            ),
        ]
        index = SkillsIndex(roots=["/workspace/.skills"], skills=skills)
        context = index.to_prompt_context()

        assert "## Available Agent Skills" in context
        assert "1. **Web Scraper**" in context
        assert "2. **Data Analyzer**" in context
        # Each skill shows its path in the listing
        assert "/workspace/.skills/web-scraper" in context
        assert "/workspace/.skills/data-analyzer" in context
        # How to use section present
        assert "How to use skills" in context
        assert "Progressive disclosure" in context
