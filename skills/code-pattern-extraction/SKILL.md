---
name: code-pattern-extraction
description: Extract reusable design and implementation patterns from codebases into Skills. Use when asked to analyze code for patterns, document architectural decisions, create transferrable implementation guides, or extract knowledge into Skills. Transforms working implementations into comprehensive, reusable Skills that can be applied to new projects.
---

# Code Pattern Extraction Skill

You are an expert software architect specializing in extracting reusable patterns from codebases. Your goal is to transform working implementations into comprehensive Skills that can be applied to new projects.

## Core Philosophy

Patterns are **transferable knowledge** - they capture not just *what* code does, but *why* it works, *when* to use it, and *how* to adapt it. A good pattern extraction:

1. **Abstracts the essence** while preserving critical details
2. **Documents the context** in which the pattern applies
3. **Provides concrete examples** from the source implementation
4. **Identifies edge cases** and common pitfalls
5. **Includes testing strategies** to verify correct implementation

---

## Agent Skills Format Specification

This section defines the official Agent Skills format. All extracted patterns MUST follow this specification.

### Directory Structure

A skill is a folder containing at minimum a `SKILL.md` file:

```
skill-name/
├── SKILL.md          # Required: instructions + metadata
├── scripts/          # Optional: executable code
├── references/       # Optional: additional documentation
└── assets/           # Optional: templates, images, data files
```

### SKILL.md Format

The `SKILL.md` file MUST contain YAML frontmatter followed by Markdown content.

#### Required Frontmatter

```yaml
---
name: skill-name
description: A description of what this skill does and when to use it.
---
```

#### Optional Frontmatter

```yaml
---
name: pdf-processing
description: Extract text and tables from PDF files, fill forms, merge documents.
license: Apache-2.0
compatibility: Requires pdfplumber, pypdf. No network access needed.
metadata:
  author: example-org
  version: "1.0"
allowed-tools: Bash(git:*) Read Edit
---
```

### Frontmatter Field Specifications

#### `name` Field (Required)

| Constraint | Requirement |
|------------|-------------|
| Length | 1-64 characters |
| Characters | Lowercase letters (`a-z`), numbers (`0-9`), and hyphens (`-`) only |
| Hyphens | Cannot start or end with hyphen; no consecutive hyphens (`--`) |
| Directory | Must match the parent directory name |

**Valid**: `pdf-processing`, `data-analysis`, `oauth-credential-injection`
**Invalid**: `PDF-Processing` (uppercase), `-pdf` (starts with hyphen), `pdf_processing` (underscore)

#### `description` Field (Required)

| Constraint | Requirement |
|------------|-------------|
| Length | 1-1024 characters |
| Content | Must describe BOTH what the skill does AND when to use it |
| Keywords | Include specific terms that help agents identify relevant tasks |

**Good Example:**
```yaml
description: Extracts text and tables from PDF files, fills PDF forms, and merges multiple PDFs. Use when working with PDF documents or when the user mentions PDFs, forms, or document extraction.
```

**Poor Example:**
```yaml
description: Helps with PDFs.
```

#### Optional Fields

| Field | Constraints | Example |
|-------|-------------|---------|
| `license` | License name or file reference | `MIT`, `Apache-2.0` |
| `compatibility` | Max 500 chars, environment requirements | `Requires git, docker` |
| `metadata` | Key-value mapping | `author: org`, `version: "1.0"` |
| `allowed-tools` | Space-delimited tool list (experimental) | `Bash(git:*) Read Edit` |

### Optional Directories

#### scripts/

Contains executable code that agents can run:
- Should be self-contained or clearly document dependencies
- Include helpful error messages
- Handle edge cases gracefully
- Common languages: Python, Bash, JavaScript

#### references/

Contains additional documentation loaded on demand:
- `REFERENCE.md` - Detailed technical reference
- Domain-specific files (`finance.md`, `legal.md`, etc.)
- Keep files focused; smaller files = less context usage

#### assets/

Contains static resources:
- Templates (document templates, configuration templates)
- Images (diagrams, examples)
- Data files (lookup tables, schemas)

### Progressive Disclosure

Skills use progressive disclosure to manage context efficiently:

| Level | Content | Token Budget | When Loaded |
|-------|---------|--------------|-------------|
| Metadata | `name` and `description` | ~100 tokens per skill | At startup |
| Instructions | Full `SKILL.md` body | <5000 tokens recommended | When skill is activated |
| Resources | Files in `scripts/`, `references/`, `assets/` | As needed | Only when required |

**Guidelines:**
- Keep `SKILL.md` under **500 lines**
- Move detailed reference material to separate files
- Keep file references **one level deep** from `SKILL.md`
- Avoid deeply nested reference chains

### File References

Use relative paths from the skill root:

```markdown
See [the reference guide](references/REFERENCE.md) for details.

Run the extraction script:
scripts/extract.py
```

---

## Pattern Extraction Workflow

### Phase 1: Deep Analysis

Before extracting any patterns, perform comprehensive analysis:

**1. Code Exploration**
```
1. Identify the feature's entry points (controllers, services, commands)
2. Trace the data flow through the system
3. Map the class/module relationships
4. Note the dependencies and their roles
5. Identify configuration points (YAML, environment, database)
```

**2. Documentation Review**
```
1. Read feature specs in docs/features/
2. Review JTBD (Jobs To Be Done) playbooks in docs/jtbd/
3. Check blog posts for debugging insights in docs/blog/
4. Review manual test documentation in docs/manual-tests/
5. Examine any walkthroughs in docs/walkthroughs/
```

**3. Test Analysis**
```
1. Review test files to understand expected behaviors
2. Note edge cases covered by tests
3. Identify testing patterns specific to this feature
4. Document integration/system test strategies
```

### Phase 2: Pattern Identification

Categorize the patterns you find:

**Structural Patterns**
- Model relationships and associations
- Inheritance hierarchies (STI, polymorphism)
- Module composition and concerns
- Service object organization

**Behavioral Patterns**
- Data flow and transformations
- Event handling and callbacks
- Error handling strategies
- Async processing patterns

**Integration Patterns**
- External API communication
- Authentication/authorization flows
- Configuration injection
- Credential management

**UI/UX Patterns**
- Controller conventions
- View organization
- JavaScript/Stimulus patterns
- Form handling

**Testing Patterns**
- Factory strategies
- Mock/stub approaches
- System test synchronization
- Integration test isolation

### Phase 3: Skill Creation

For each significant pattern, create a Skill following the official format.

#### Complete Skill Template

```markdown
---
name: pattern-name-here
description: Concise description of what this pattern does and when to use it. Include keywords that help agents identify relevant tasks.
license: MIT
metadata:
  author: your-org
  version: "1.0"
---

# Pattern Name

## Problem Statement
What problem does this pattern solve? (2-3 sentences)

## When to Use
- Specific scenario where this pattern applies
- Another indicator that this pattern is relevant
- Keywords: [terms someone might search for]

## Core Concept
Brief explanation of the pattern's essence. Focus on the "why" not just the "what". (2-3 sentences max)

## Implementation Guide

### Key Components
| File/Class | Role |
|------------|------|
| `app/models/foo.rb` | Main model implementing X |
| `app/services/bar_service.rb` | Orchestrates Y |

### Step-by-Step Implementation

#### Step 1: Create the base model
```ruby
# app/models/foo.rb
class Foo < ApplicationRecord
  # Example code from the source implementation
end
```

#### Step 2: Add the service layer
```ruby
# app/services/bar_service.rb
class BarService
  # Continue with implementation...
end
```

### Configuration
```yaml
# config/settings.yml
feature:
  enabled: true
  option: value
```

### Integration Points
- Connects to X via Y
- Depends on Z being configured

## Testing Strategy

### Unit Tests
```ruby
RSpec.describe Foo do
  it "does the thing" do
    # Test example
  end
end
```

### Integration Tests
How to test the pattern works end-to-end.

### Common Test Pitfalls
- Watch out for X when testing
- Remember to mock Y

## Common Pitfalls

1. **Pitfall Name**: Description and how to avoid it
2. **Another Pitfall**: What goes wrong and the fix

## Variations

### Variation Name
When to use this variation and how it differs from the base pattern.

## Debugging Tips

- Check X when you see error Y
- Use `rails console` to verify Z

## Related Patterns
- [related-pattern-name](../related-pattern-name/SKILL.md) - Often used together
- [alternative-pattern](../alternative-pattern/SKILL.md) - Use when conditions differ
```

### Phase 4: Skill Organization

Save extracted Skills to `.claude/skills/` with directory names matching the skill name:

```
.claude/skills/
├── oauth-credential-injection/
│   ├── SKILL.md
│   └── references/
│       └── oauth-providers.md
├── mcp-server-integration/
│   ├── SKILL.md
│   └── scripts/
│       └── validate-server.py
├── multi-tenant-data-access/
│   └── SKILL.md
└── rails-controller-testing/
    ├── SKILL.md
    └── references/
        └── authentication-helpers.md
```

---

## Quality Checklist

Before finalizing any Skill, verify:

### Format Compliance
- [ ] `name` is lowercase with hyphens only (no underscores, no uppercase)
- [ ] `name` matches the parent directory name
- [ ] `name` is 1-64 characters, doesn't start/end with hyphen
- [ ] `description` is 1-1024 characters
- [ ] `description` describes both WHAT and WHEN to use
- [ ] SKILL.md is under 500 lines
- [ ] File references are relative and one level deep

### Content Quality
- [ ] **Transferable**: Can be applied to a completely new project
- [ ] **Self-Contained**: All necessary context is included
- [ ] **Actionable**: Clear steps to implement
- [ ] **Tested**: Testing strategy is documented
- [ ] **Edge Cases**: Common pitfalls are documented
- [ ] **Concrete**: Includes real code examples
- [ ] **Concise**: No unnecessary explanation (Claude is smart)

---

## Example Pattern Categories

Common patterns to look for:

| Category | Examples |
|----------|----------|
| **Auth** | OAuth injection, multi-tenant isolation, RBAC |
| **LLM/AI** | Client abstraction, provider switching, streaming, tool calling |
| **External Services** | API clients, webhooks, retry/backoff |
| **Data Modeling** | STI, polymorphic associations, JSONB config |
| **Background Jobs** | Idempotency, error handling, progress tracking |
| **Testing** | Factory patterns, auth helpers, system test sync |

---

## Output Format

When extracting patterns, provide:

1. **Summary**: Brief overview of patterns found
2. **Pattern Skills**: Complete SKILL.md files for each pattern (following the spec above)
3. **Organization**: Suggested directory structure
4. **Dependencies**: Any patterns that depend on others

## Utility Scripts

This skill includes helper scripts for creating and validating skills:

### Initialize a New Skill

```bash
python scripts/init_skill.py <skill-name> --path <output-dir> [--resources scripts,references,assets]
```

Examples:
```bash
python scripts/init_skill.py oauth-injection --path .claude/skills
python scripts/init_skill.py mcp-integration --path .claude/skills --resources scripts,references
```

### Validate and Package a Skill

```bash
python scripts/package_skill.py <path/to/skill> [output-dir]
python scripts/package_skill.py .claude/skills/my-skill --validate-only
```

The packager validates name format, description quality, and directory structure before creating a `.skill` file.

---

## Reference Guides

For detailed patterns, see:

- **[Workflow Patterns](references/workflows.md)** - Sequential, conditional, iterative, and validation workflows
- **[Output Patterns](references/output-patterns.md)** - Templates, code examples, documentation patterns

---

## What NOT to Include in Skills

A skill should only contain essential files. Do NOT create:

| File | Why Not |
|------|---------|
| `README.md` | Put everything in SKILL.md |
| `CHANGELOG.md` | Use `metadata.version` if needed |
| `INSTALLATION_GUIDE.md` | Skills aren't installed by users |
| `CONTRIBUTING.md` | Skills are self-contained |
| `QUICK_REFERENCE.md` | Use references/ directory instead |

**Content Anti-Patterns:**
- ❌ Excessive explanation - Claude is smart, be concise
- ❌ Vague descriptions - Be specific about triggers
- ❌ Missing "when to use" - Always include trigger conditions
- ❌ Deeply nested references - Keep one level deep
- ❌ Duplicate information - Single source of truth

---

## Iteration Workflow

After creating a skill, iterate based on real usage:

1. **Use** the skill on real tasks
2. **Notice** struggles or inefficiencies
3. **Identify** how SKILL.md or resources should be updated
4. **Implement** changes
5. **Validate** with `package_skill.py --validate-only`
6. **Test** again on similar tasks

---

## Important Notes

- **Follow the spec exactly** - name format, description length, directory structure
- Focus on patterns that are **truly reusable** - not just implementation details
- Include **enough context** that Claude could reimplement in a new project
- Don't over-abstract - **concrete examples** are valuable
- Consider **variations** of the pattern for different scenarios
- Always include **testing strategies** - untestable patterns are incomplete
- Keep SKILL.md under **500 lines** - use `references/` for additional detail
