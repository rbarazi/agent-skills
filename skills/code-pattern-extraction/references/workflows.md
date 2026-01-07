# Workflow Patterns for Skills

This reference provides established patterns for designing skill workflows.

## Table of Contents

- [Sequential Workflows](#sequential-workflows)
- [Conditional Workflows](#conditional-workflows)
- [Iterative Workflows](#iterative-workflows)
- [Validation Workflows](#validation-workflows)

---

## Sequential Workflows

Use when tasks must be completed in a specific order.

### Pattern: Numbered Steps with Checkpoints

```markdown
## Workflow

### Step 1: Analyze the input
1. Read all source files
2. Identify key components
3. **Checkpoint**: List components found before proceeding

### Step 2: Transform data
1. Apply transformation A
2. Apply transformation B
3. **Checkpoint**: Verify transformations were applied correctly

### Step 3: Generate output
1. Create output file
2. Validate output format
3. **Checkpoint**: Confirm output matches expected structure
```

### Pattern: Prerequisites with Validation

```markdown
## Prerequisites

Before starting, ensure:
- [ ] Input file exists at `path/to/input`
- [ ] Required tool X is installed (`which tool-x`)
- [ ] Configuration file is present

## Workflow

Only proceed if all prerequisites are met.
```

---

## Conditional Workflows

Use when different paths apply based on context.

### Pattern: Decision Tree

```markdown
## Workflow Selection

Determine the appropriate workflow:

**Creating new content?**
→ Follow [Creation Workflow](#creation-workflow)

**Editing existing content?**
→ Follow [Editing Workflow](#editing-workflow)

**Migrating from old format?**
→ Follow [Migration Workflow](#migration-workflow)

### Creation Workflow
...

### Editing Workflow
...

### Migration Workflow
...
```

### Pattern: Feature Detection

```markdown
## Workflow

1. Detect environment:
   - Check for file X → Use approach A
   - Check for file Y → Use approach B
   - Neither found → Use default approach C

2. Execute selected approach
```

---

## Iterative Workflows

Use when refinement through multiple passes is needed.

### Pattern: Analyze-Implement-Verify Loop

```markdown
## Workflow

Repeat until complete:

1. **Analyze**: Identify the next item to process
2. **Implement**: Make the necessary changes
3. **Verify**: Confirm the change was successful
4. **Continue**: If more items remain, return to step 1

### Exit Condition
Stop when all items have been processed and verified.
```

### Pattern: Progressive Refinement

```markdown
## Workflow

### Pass 1: Structure
- Create overall structure
- Define major components
- Skip details for now

### Pass 2: Content
- Fill in component details
- Add implementation code
- Leave edge cases for later

### Pass 3: Polish
- Handle edge cases
- Add error handling
- Optimize performance
```

---

## Validation Workflows

Use when correctness must be verified.

### Pattern: Pre-flight Checks

```markdown
## Before Making Changes

Run these checks:

```bash
# Verify current state
bin/rspec spec/relevant_spec.rb
bin/rubocop app/models/relevant_model.rb
```

If any check fails, investigate before proceeding.
```

### Pattern: Post-change Validation

```markdown
## After Making Changes

1. Run tests:
   ```bash
   bin/rspec spec/path/to/spec.rb
   ```

2. Check for regressions:
   ```bash
   bin/rspec
   ```

3. Verify code style:
   ```bash
   bin/rubocop -a
   ```

### If Validation Fails

1. Review the error message
2. Identify the root cause
3. Fix the issue
4. Re-run validation
```

### Pattern: Human Verification Points

```markdown
## Workflow

### Step 1: Generate draft
[automated steps]

### Step 2: Human Review Required
Present draft to user for approval before continuing.

**Questions to resolve:**
- Is the approach correct?
- Should any changes be made?

### Step 3: Finalize
[continue only after approval]
```

---

## Combining Patterns

Complex skills often combine multiple patterns:

```markdown
## Complete Workflow

### Phase 1: Setup (Sequential)
1. Validate prerequisites
2. Load configuration
3. Initialize state

### Phase 2: Processing (Conditional + Iterative)
For each item:
1. Determine item type (Conditional)
2. Process with appropriate handler (Sequential)
3. Verify result (Validation)
4. Continue to next item (Iterative)

### Phase 3: Finalization (Sequential + Validation)
1. Aggregate results
2. Generate output
3. Run final validation
4. Report completion
```
