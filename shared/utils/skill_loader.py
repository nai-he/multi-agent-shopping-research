"""Skills loader — implements progressive disclosure pattern from openclaw.

Loads SKILL.md files from the skills/ directory, parses YAML frontmatter,
and provides three-level access: metadata (always), body (on trigger),
resources (on demand).
"""
import yaml
import os
from pathlib import Path
from typing import Dict, List, Optional, Any


class Skill:
    """A single skill loaded from a SKILL.md file."""

    def __init__(self, skill_dir: Path):
        self.dir = skill_dir
        self.name: str = ""
        self.description: str = ""
        self.body: str = ""
        self.metadata: Dict[str, Any] = {}
        self._loaded = False

    def load_metadata(self) -> bool:
        """Level 1: Load only name and description from frontmatter."""
        skill_md = self.dir / "SKILL.md"
        if not skill_md.exists():
            return False

        content = skill_md.read_text(encoding="utf-8")
        parsed = self._parse_frontmatter(content)
        if not parsed:
            return False

        self.name = parsed.get("name", "")
        self.description = parsed.get("description", "")
        self.metadata = parsed.get("metadata", {})
        self._loaded = True
        return True

    def load_body(self) -> str:
        """Level 2: Load the full markdown body (minus frontmatter)."""
        skill_md = self.dir / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")

        # Strip YAML frontmatter
        parts = content.split("---", 2)
        if len(parts) >= 3:
            self.body = parts[2].strip()
        else:
            self.body = content.strip()
        return self.body

    def list_resources(self) -> Dict[str, List[str]]:
        """Level 3: List available resource files."""
        resources = {}
        for subdir in ["scripts", "references", "assets", "agents"]:
            subdir_path = self.dir / subdir
            if subdir_path.exists():
                resources[subdir] = [
                    p.name for p in subdir_path.iterdir() if p.is_file()
                ]
        return resources

    def get_resource(self, resource_path: str) -> Optional[str]:
        """Level 3: Load a specific resource file."""
        full_path = self.dir / resource_path
        if full_path.exists() and full_path.is_file():
            return full_path.read_text(encoding="utf-8")
        return None

    def _parse_frontmatter(self, content: str) -> Optional[Dict[str, Any]]:
        """Extract YAML frontmatter between --- delimiters."""
        if not content.startswith("---"):
            return None

        parts = content.split("---", 2)
        if len(parts) < 2:
            return None

        try:
            return yaml.safe_load(parts[1]) or {}
        except yaml.YAMLError:
            return None

    def to_metadata_dict(self) -> Dict[str, str]:
        """Return the minimal metadata for agent context."""
        return {
            "name": self.name,
            "description": self.description,
        }

    def __repr__(self):
        return f"Skill({self.name})"


class SkillLoader:
    """Loads and manages all skills from the skills/ directory."""

    def __init__(self, skills_dir: Path = None):
        if skills_dir is None:
            skills_dir = Path(__file__).parent.parent.parent / "skills"
        self.skills_dir = Path(skills_dir)
        self.skills: Dict[str, Skill] = {}

    def discover(self) -> List[Skill]:
        """Discover all skills in the skills directory."""
        self.skills = {}

        if not self.skills_dir.exists():
            return []

        for entry in self.skills_dir.iterdir():
            if entry.is_dir():
                skill = Skill(entry)
                if skill.load_metadata():
                    self.skills[skill.name] = skill

        return list(self.skills.values())

    def get_skill(self, name: str) -> Optional[Skill]:
        """Get a skill by name, loading body on demand."""
        skill = self.skills.get(name)
        if skill and not skill.body:
            skill.load_body()
        return skill

    def get_available_skills_prompt(self) -> str:
        """Generate the 'available skills' section for system prompts.

        Only includes Level 1 metadata (name + description) — minimal context usage.
        """
        if not self.skills:
            self.discover()

        lines = ["## Available Skills\n"]
        lines.append("You have access to these specialized skills. Invoke a skill when its description matches the user's task.\n")

        for skill in self.skills.values():
            lines.append(f"- **{skill.name}**: {skill.description}")

        return "\n".join(lines)

    def get_skill_context(self, name: str, include_resources: bool = False) -> str:
        """Get full skill context for injection into agent prompt.

        Args:
            name: Skill name
            include_resources: Whether to also list available resources
        """
        skill = self.get_skill(name)
        if not skill:
            return f"Skill '{name}' not found."

        parts = [
            f"# Skill: {skill.name}",
            f"Description: {skill.description}",
            "",
            skill.body,
        ]

        if include_resources:
            resources = skill.list_resources()
            if resources:
                parts.append("\n## Available Resources")
                for folder, files in resources.items():
                    parts.append(f"\n### {folder}/")
                    for f in files:
                        parts.append(f"- {folder}/{f}")

        return "\n".join(parts)

    def list_skills(self) -> List[Dict[str, str]]:
        """List all installed skills with metadata."""
        if not self.skills:
            self.discover()
        return [
            {
                "name": s.name,
                "description": s.description,
                "agent": s.metadata.get("agent", ""),
                "priority": str(s.metadata.get("priority", "")),
                "requires": str(s.metadata.get("requires", "")),
            }
            for s in self.skills.values()
        ]


# Singleton instance
_loader: Optional[SkillLoader] = None


def get_skill_loader(skills_dir: Path = None) -> SkillLoader:
    """Get or create the skill loader singleton."""
    global _loader
    if _loader is None:
        _loader = SkillLoader(skills_dir)
        _loader.discover()
    return _loader


def get_skills_context() -> str:
    """Get the skills context for system prompts."""
    loader = get_skill_loader()
    return loader.get_available_skills_prompt()
