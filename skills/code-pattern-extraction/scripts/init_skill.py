#!/usr/bin/env python3
"""
Initialize a new skill directory with proper structure.

Usage:
    python init_skill.py <skill-name> --path <output-directory> [--resources scripts,references,assets]

Examples:
    python init_skill.py oauth-injection --path .claude/skills
    python init_skill.py mcp-integration --path .claude/skills --resources scripts,references
"""

import argparse
import os
import re
import sys
from pathlib import Path


def validate_skill_name(name: str) -> tuple[bool, str]:
    """Validate skill name against Agent Skills specification."""
    if not name:
        return False, "Name cannot be empty"

    if len(name) > 64:
        return False, f"Name must be 64 characters or less (got {len(name)})"

    if not re.match(r'^[a-z0-9]+(-[a-z0-9]+)*$', name):
        return False, "Name must be lowercase letters, numbers, and hyphens only. Cannot start/end with hyphen or have consecutive hyphens."

    return True, ""


def create_skill_md(skill_name: str, resources: list[str]) -> str:
    """Generate SKILL.md template content."""

    # Build references section if references are included
    references_section = ""
    if "references" in resources:
        references_section = """
## References

For detailed information, see:
- [REFERENCE.md](references/REFERENCE.md) - Detailed technical reference

<!-- TODO: Add references as needed -->
"""

    # Build scripts section if scripts are included
    scripts_section = ""
    if "scripts" in resources:
        scripts_section = """
## Scripts

Available utility scripts:
- `scripts/example.py` - Example script (TODO: replace or remove)

<!-- TODO: Add script documentation as needed -->
"""

    template = f'''---
name: {skill_name}
description: TODO - Describe what this skill does AND when to use it. Include keywords that help agents identify relevant tasks. (Max 1024 characters)
metadata:
  author: TODO
  version: "1.0"
---

# {skill_name.replace("-", " ").title()}

## Problem Statement

<!-- TODO: What problem does this skill solve? (2-3 sentences) -->

## When to Use

- <!-- TODO: Specific scenario where this skill applies -->
- <!-- TODO: Another indicator that this skill is relevant -->
- Keywords: <!-- TODO: terms someone might search for -->

## Core Concept

<!-- TODO: Brief explanation of the skill's essence. Focus on the "why" not just the "what". (2-3 sentences max) -->

## Implementation Guide

### Key Components

| File/Class | Role |
|------------|------|
| <!-- TODO --> | <!-- TODO --> |

### Step-by-Step Implementation

#### Step 1: <!-- TODO -->

```ruby
# TODO: Add implementation code
```

### Configuration

```yaml
# TODO: Add configuration if needed
```
{references_section}{scripts_section}
## Testing Strategy

### Unit Tests

```ruby
# TODO: Add test examples
```

### Common Test Pitfalls

- <!-- TODO: What to watch out for -->

## Common Pitfalls

1. **<!-- TODO -->**: Description and how to avoid it

## Debugging Tips

- <!-- TODO: Add debugging tips -->

## Related Patterns

- <!-- TODO: Link to related skills -->
'''
    return template


def create_reference_template() -> str:
    """Generate reference file template."""
    return '''# Reference

## Overview

<!-- TODO: Add detailed reference content here -->

## Table of Contents

- [Section 1](#section-1)
- [Section 2](#section-2)

## Section 1

<!-- TODO -->

## Section 2

<!-- TODO -->
'''


def create_script_template(skill_name: str) -> str:
    """Generate example script template."""
    return f'''#!/usr/bin/env python3
"""
Example script for {skill_name} skill.

TODO: Replace this with actual script functionality or delete if not needed.
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="Example script")
    parser.add_argument("input", help="Input file or value")
    args = parser.parse_args()

    # TODO: Implement script logic
    print(f"Processing: {{args.input}}")


if __name__ == "__main__":
    main()
'''


def init_skill(skill_name: str, output_path: str, resources: list[str]) -> None:
    """Initialize a new skill directory."""

    # Validate skill name
    valid, error = validate_skill_name(skill_name)
    if not valid:
        print(f"Error: Invalid skill name - {error}")
        sys.exit(1)

    # Create skill directory
    skill_dir = Path(output_path) / skill_name

    if skill_dir.exists():
        print(f"Error: Skill directory already exists: {skill_dir}")
        sys.exit(1)

    skill_dir.mkdir(parents=True)
    print(f"Created skill directory: {skill_dir}")

    # Create SKILL.md
    skill_md_path = skill_dir / "SKILL.md"
    skill_md_path.write_text(create_skill_md(skill_name, resources))
    print(f"Created: {skill_md_path}")

    # Create optional resource directories
    if "scripts" in resources:
        scripts_dir = skill_dir / "scripts"
        scripts_dir.mkdir()
        script_path = scripts_dir / "example.py"
        script_path.write_text(create_script_template(skill_name))
        script_path.chmod(0o755)
        print(f"Created: {scripts_dir}/")

    if "references" in resources:
        refs_dir = skill_dir / "references"
        refs_dir.mkdir()
        ref_path = refs_dir / "REFERENCE.md"
        ref_path.write_text(create_reference_template())
        print(f"Created: {refs_dir}/")

    if "assets" in resources:
        assets_dir = skill_dir / "assets"
        assets_dir.mkdir()
        (assets_dir / ".gitkeep").touch()
        print(f"Created: {assets_dir}/")

    print(f"\n✅ Skill '{skill_name}' initialized successfully!")
    print(f"\nNext steps:")
    print(f"  1. Edit {skill_md_path} - Fill in the TODO sections")
    if "scripts" in resources:
        print(f"  2. Add/update scripts in {skill_dir}/scripts/")
    if "references" in resources:
        print(f"  3. Add reference documentation in {skill_dir}/references/")
    print(f"  4. Run package_skill.py to validate and package when ready")


def main():
    parser = argparse.ArgumentParser(
        description="Initialize a new skill directory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s oauth-injection --path .claude/skills
  %(prog)s mcp-integration --path .claude/skills --resources scripts,references
        """
    )
    parser.add_argument("skill_name", help="Name of the skill (lowercase, hyphens only)")
    parser.add_argument("--path", required=True, help="Output directory for the skill")
    parser.add_argument(
        "--resources",
        default="",
        help="Comma-separated list of resource directories to create (scripts,references,assets)"
    )

    args = parser.parse_args()

    resources = [r.strip() for r in args.resources.split(",") if r.strip()]

    init_skill(args.skill_name, args.path, resources)


if __name__ == "__main__":
    main()
