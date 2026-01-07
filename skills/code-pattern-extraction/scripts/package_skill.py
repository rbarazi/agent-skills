#!/usr/bin/env python3
"""
Validate and package a skill into a distributable .skill file.

Usage:
    python package_skill.py <path/to/skill-folder> [output-directory]

Examples:
    python package_skill.py .claude/skills/oauth-injection
    python package_skill.py .claude/skills/oauth-injection ./dist
"""

import argparse
import os
import re
import sys
import zipfile
from pathlib import Path

import yaml


class ValidationError:
    def __init__(self, message: str, severity: str = "error"):
        self.message = message
        self.severity = severity  # "error" or "warning"


def validate_skill_name(name: str, directory_name: str) -> list[ValidationError]:
    """Validate skill name against Agent Skills specification."""
    errors = []

    if not name:
        errors.append(ValidationError("name field is required"))
        return errors

    if len(name) > 64:
        errors.append(ValidationError(f"name must be 64 characters or less (got {len(name)})"))

    if not re.match(r'^[a-z0-9]+(-[a-z0-9]+)*$', name):
        errors.append(ValidationError(
            "name must be lowercase letters, numbers, and hyphens only. "
            "Cannot start/end with hyphen or have consecutive hyphens."
        ))

    if name != directory_name:
        errors.append(ValidationError(
            f"name '{name}' must match directory name '{directory_name}'"
        ))

    return errors


def validate_description(description: str) -> list[ValidationError]:
    """Validate description against Agent Skills specification."""
    errors = []

    if not description:
        errors.append(ValidationError("description field is required"))
        return errors

    if len(description) > 1024:
        errors.append(ValidationError(
            f"description must be 1024 characters or less (got {len(description)})"
        ))

    # Check for quality indicators
    desc_lower = description.lower()

    if len(description) < 50:
        errors.append(ValidationError(
            "description is very short. Include both WHAT the skill does and WHEN to use it.",
            severity="warning"
        ))

    if "todo" in desc_lower:
        errors.append(ValidationError("description contains TODO placeholder"))

    # Check for "when to use" indicators
    when_indicators = ["use when", "use for", "when the user", "when you need", "triggers when"]
    has_when = any(indicator in desc_lower for indicator in when_indicators)
    if not has_when:
        errors.append(ValidationError(
            "description should explain WHEN to use the skill (e.g., 'Use when...')",
            severity="warning"
        ))

    return errors


def validate_frontmatter(content: str, directory_name: str) -> tuple[dict, list[ValidationError]]:
    """Parse and validate YAML frontmatter."""
    errors = []

    # Check for frontmatter delimiters
    if not content.startswith("---"):
        errors.append(ValidationError("SKILL.md must start with YAML frontmatter (---)"))
        return {}, errors

    # Find end of frontmatter
    end_match = re.search(r'\n---\s*\n', content[3:])
    if not end_match:
        errors.append(ValidationError("SKILL.md frontmatter must be closed with ---"))
        return {}, errors

    frontmatter_text = content[3:end_match.start() + 3]

    try:
        frontmatter = yaml.safe_load(frontmatter_text)
        if not isinstance(frontmatter, dict):
            errors.append(ValidationError("Frontmatter must be a YAML dictionary"))
            return {}, errors
    except yaml.YAMLError as e:
        errors.append(ValidationError(f"Invalid YAML in frontmatter: {e}"))
        return {}, errors

    # Validate required fields
    errors.extend(validate_skill_name(frontmatter.get("name", ""), directory_name))
    errors.extend(validate_description(frontmatter.get("description", "")))

    # Validate optional fields
    if "compatibility" in frontmatter:
        compat = frontmatter["compatibility"]
        if len(str(compat)) > 500:
            errors.append(ValidationError(
                f"compatibility must be 500 characters or less (got {len(str(compat))})"
            ))

    return frontmatter, errors


def validate_skill_md(skill_path: Path) -> list[ValidationError]:
    """Validate SKILL.md content."""
    errors = []
    skill_md = skill_path / "SKILL.md"

    if not skill_md.exists():
        errors.append(ValidationError("SKILL.md file is required"))
        return errors

    content = skill_md.read_text()
    directory_name = skill_path.name

    # Validate frontmatter
    frontmatter, fm_errors = validate_frontmatter(content, directory_name)
    errors.extend(fm_errors)

    # Check line count
    lines = content.split('\n')
    if len(lines) > 500:
        errors.append(ValidationError(
            f"SKILL.md should be under 500 lines (got {len(lines)}). "
            "Consider moving content to references/",
            severity="warning"
        ))

    # Check for TODO placeholders in body
    if "<!-- TODO" in content or "# TODO" in content:
        errors.append(ValidationError(
            "SKILL.md contains TODO placeholders that should be filled in",
            severity="warning"
        ))

    return errors


def validate_structure(skill_path: Path) -> list[ValidationError]:
    """Validate skill directory structure."""
    errors = []

    # Check for disallowed files
    disallowed = ["README.md", "CHANGELOG.md", "INSTALLATION_GUIDE.md", "QUICK_REFERENCE.md"]
    for filename in disallowed:
        if (skill_path / filename).exists():
            errors.append(ValidationError(
                f"'{filename}' should not be included in a skill. "
                "All documentation should be in SKILL.md or references/"
            ))

    # Check resource directories
    for dirname in ["scripts", "references", "assets"]:
        dir_path = skill_path / dirname
        if dir_path.exists() and not dir_path.is_dir():
            errors.append(ValidationError(f"'{dirname}' must be a directory, not a file"))

    # Validate scripts are executable (Unix only)
    scripts_dir = skill_path / "scripts"
    if scripts_dir.exists():
        for script in scripts_dir.glob("*.py"):
            if not os.access(script, os.X_OK):
                errors.append(ValidationError(
                    f"Script '{script.name}' is not executable. Run: chmod +x {script}",
                    severity="warning"
                ))

    return errors


def validate_skill(skill_path: Path) -> list[ValidationError]:
    """Run all validations on a skill."""
    errors = []

    if not skill_path.exists():
        errors.append(ValidationError(f"Skill path does not exist: {skill_path}"))
        return errors

    if not skill_path.is_dir():
        errors.append(ValidationError(f"Skill path must be a directory: {skill_path}"))
        return errors

    errors.extend(validate_skill_md(skill_path))
    errors.extend(validate_structure(skill_path))

    return errors


def package_skill(skill_path: Path, output_dir: Path) -> Path:
    """Create a .skill package from the skill directory."""
    skill_name = skill_path.name
    output_file = output_dir / f"{skill_name}.skill"

    output_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_path in skill_path.rglob('*'):
            if file_path.is_file():
                # Skip hidden files and __pycache__
                if any(part.startswith('.') or part == '__pycache__' for part in file_path.parts):
                    continue
                arcname = file_path.relative_to(skill_path.parent)
                zf.write(file_path, arcname)

    return output_file


def main():
    parser = argparse.ArgumentParser(
        description="Validate and package a skill",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s .claude/skills/oauth-injection
  %(prog)s .claude/skills/oauth-injection ./dist
        """
    )
    parser.add_argument("skill_path", help="Path to the skill directory")
    parser.add_argument("output_dir", nargs="?", default=".", help="Output directory for .skill file")
    parser.add_argument("--validate-only", action="store_true", help="Only validate, don't package")

    args = parser.parse_args()

    skill_path = Path(args.skill_path).resolve()
    output_dir = Path(args.output_dir).resolve()

    print(f"Validating skill: {skill_path}")
    print("-" * 50)

    errors = validate_skill(skill_path)

    # Separate errors and warnings
    critical_errors = [e for e in errors if e.severity == "error"]
    warnings = [e for e in errors if e.severity == "warning"]

    # Print warnings
    for warning in warnings:
        print(f"⚠️  Warning: {warning.message}")

    # Print errors
    for error in critical_errors:
        print(f"❌ Error: {error.message}")

    print("-" * 50)

    if critical_errors:
        print(f"\n❌ Validation failed with {len(critical_errors)} error(s)")
        if warnings:
            print(f"   (plus {len(warnings)} warning(s))")
        sys.exit(1)

    if warnings:
        print(f"\n⚠️  Validation passed with {len(warnings)} warning(s)")
    else:
        print("\n✅ Validation passed!")

    if args.validate_only:
        return

    # Package the skill
    print(f"\nPackaging skill...")
    output_file = package_skill(skill_path, output_dir)
    print(f"✅ Created: {output_file}")
    print(f"   Size: {output_file.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
