# Output Patterns for Skills

This reference provides patterns for structuring skill outputs consistently.

## Table of Contents

- [Skill Template Patterns](#skill-template-patterns)
- [Code Example Patterns](#code-example-patterns)
- [Documentation Patterns](#documentation-patterns)
- [Quality Checklist Patterns](#quality-checklist-patterns)

---

## Skill Template Patterns

### Pattern: Minimal Viable Skill

For simple skills that need minimal context:

```markdown
---
name: skill-name
description: What it does. Use when [trigger conditions].
---

# Skill Name

## Quick Start

[Essential instructions - 5-10 lines max]

## Common Variations

- **Variation A**: [brief description]
- **Variation B**: [brief description]
```

### Pattern: Full Implementation Skill

For complex skills requiring detailed guidance:

```markdown
---
name: skill-name
description: Comprehensive description with triggers.
metadata:
  author: org-name
  version: "1.0"
---

# Skill Name

## Problem Statement
[2-3 sentences]

## When to Use
- [Trigger 1]
- [Trigger 2]

## Implementation Guide

### Key Components
[Table of files/classes]

### Step-by-Step
[Numbered steps with code]

## Testing Strategy
[How to verify]

## Common Pitfalls
[What to avoid]

## References
- [Link to reference files]
```

### Pattern: Multi-Variant Skill

For skills supporting multiple frameworks/approaches:

```markdown
---
name: skill-name
description: Supports X, Y, and Z. Use when [triggers].
---

# Skill Name

## Variant Selection

Choose your variant:
- **X**: [when to use] → See [references/x.md](references/x.md)
- **Y**: [when to use] → See [references/y.md](references/y.md)
- **Z**: [when to use] → See [references/z.md](references/z.md)

## Common Workflow

[Steps that apply to all variants]
```

---

## Code Example Patterns

### Pattern: Before/After Comparison

```markdown
## Example

**Before:**
```ruby
# Problem: Tightly coupled code
class UserController
  def create
    user = User.new(params[:user])
    Mailer.welcome(user).deliver if user.save
  end
end
```

**After:**
```ruby
# Solution: Service object extraction
class UserController
  def create
    CreateUserService.call(params[:user])
  end
end
```
```

### Pattern: Annotated Code Block

```markdown
```ruby
class OAuth::CredentialInjector
  # 1. Define which credentials this tool needs
  REQUIRED_CREDENTIALS = [:slack_token, :team_id]

  # 2. Inject at call time, not configuration time
  def inject(tool_call, context)
    return {} unless tool_requires_credentials?(tool_call)

    # 3. Build credentials from context
    build_credentials(context)
  end

  private

  # 4. Check tool configuration for requirement flag
  def tool_requires_credentials?(tool_call)
    tool_call.tool.config&.requires_oauth?
  end
end
```
```

### Pattern: Progressive Complexity

```markdown
## Basic Usage

```ruby
# Simple case - just call the service
result = MyService.call(input)
```

## With Options

```ruby
# Add options when needed
result = MyService.call(input, validate: true, notify: false)
```

## Full Configuration

```ruby
# Complete configuration for complex cases
result = MyService.new(
  input: input,
  validator: CustomValidator.new,
  notifier: SlackNotifier.new,
  options: { retry: 3, timeout: 30 }
).call
```
```

---

## Documentation Patterns

### Pattern: Quick Reference Table

```markdown
## Quick Reference

| Scenario | Action | Example |
|----------|--------|---------|
| New record | Use `create` | `User.create(attrs)` |
| Update existing | Use `update` | `user.update(attrs)` |
| Conditional | Use `find_or_create_by` | `User.find_or_create_by(email: x)` |
```

### Pattern: Decision Matrix

```markdown
## When to Use What

| Condition | Low Complexity | High Complexity |
|-----------|---------------|-----------------|
| Single model | Direct ActiveRecord | Service object |
| Multiple models | Transaction block | Orchestrator service |
| External API | API client | Background job + client |
```

### Pattern: Troubleshooting Guide

```markdown
## Troubleshooting

### Error: "Connection refused"

**Cause**: Database not running

**Fix**:
```bash
docker-compose up -d postgres
```

### Error: "Invalid credentials"

**Cause**: OAuth token expired

**Fix**:
1. Check token expiry in database
2. Trigger re-authentication flow
3. Retry operation
```

---

## Quality Checklist Patterns

### Pattern: Pre-Submission Checklist

```markdown
## Before Completing

- [ ] All TODOs resolved
- [ ] Code compiles/runs without errors
- [ ] Tests pass
- [ ] No hardcoded values that should be configurable
- [ ] Error handling in place
```

### Pattern: Review Checklist

```markdown
## Self-Review Questions

1. **Clarity**: Would another developer understand this?
2. **Completeness**: Are all edge cases handled?
3. **Correctness**: Does it actually solve the problem?
4. **Consistency**: Does it follow existing patterns?
5. **Conciseness**: Is there any unnecessary code?
```

### Pattern: Skill Quality Checklist

```markdown
## Skill Quality Verification

### Format Compliance
- [ ] `name` is lowercase with hyphens only
- [ ] `name` matches directory name
- [ ] `description` < 1024 chars
- [ ] `description` includes WHAT and WHEN
- [ ] SKILL.md < 500 lines

### Content Quality
- [ ] Transferable to new project
- [ ] Self-contained (no missing context)
- [ ] Actionable steps
- [ ] Testing strategy included
- [ ] Common pitfalls documented
- [ ] Real code examples
```

---

## Anti-Patterns to Avoid

### What NOT to Include

❌ **README.md** - Put everything in SKILL.md
❌ **CHANGELOG.md** - Version in metadata if needed
❌ **INSTALLATION_GUIDE.md** - Not for end users
❌ **CONTRIBUTING.md** - Skills are self-contained
❌ **LICENSE** at top level - Use `license:` in frontmatter

### Content Anti-Patterns

❌ **Excessive explanation** - Claude is smart, be concise
❌ **Vague descriptions** - Be specific about triggers
❌ **Missing "when to use"** - Always include triggers
❌ **Deeply nested references** - Keep one level deep
❌ **Duplicate information** - Single source of truth
