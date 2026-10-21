# Documentation requirements

A standing, project-wide bar that every change must clear before it counts as done. Unlike acceptance criteria, which vary per task and answer "did we build the right thing?", the Definition of Done is the same every time and answers "is this finished to our standard?".

## Definition of Done vs. Acceptance Criteria

| | Acceptance Criteria | Definition of Done |
|---|---|---|
| Scope | Specific to one task or spec | Applies to every increment |
| Changes | Different for each item | Fixed and reused |
| Answers | "Did we build *this thing*?" | "Is it *ready*?" |
| Owner | Defined when planning the task | Defined once for the project |
| Example | "User can reset password via email link" | "Tests pass, no regressions, docs updated" |

The two are complementary. A task is done only when **its** acceptance criteria are met **and** the standing Definition of Done is satisfied. Skipping either leaves work that looks finished but is not.

## The Standing Checklist

Apply this to every change before declaring it done.

### Correctness
- [ ] All acceptance criteria for the task are met
- [ ] Code runs and behaves as intended, verified at runtime, not just compiled or typechecked
- [ ] New behavior is covered by tests that fail without the change and pass with it
- [ ] Existing tests still pass; no regressions introduced
- [ ] Edge cases and error paths are handled, not just the happy path

### Quality
- [ ] Code reveals intent through naming and structure; no comments needed to explain *what* it does
- [ ] No duplicated business logic
- [ ] No dead code, debug output, or commented-out blocks left behind
- [ ] Changes are scoped to the task; no unrelated refactors snuck in
- [ ] Linting and formatting pass

### Integration
- [ ] Change works with the rest of the system, not just in isolation
- [ ] Database migrations, config changes, and feature flags are accounted for
- [ ] Backward compatibility considered for any public interface or API change

### Documentation
- [ ] Public interfaces, APIs, and user-facing behavior are documented
- [ ] Documentation describes the current state in timeless language, not the change history

### Ship-readiness
- [ ] The human has reviewed and approved before merge or deploy

## How to Apply

- **Per task**: confirm the Correctness and Quality sections before checking the task off.
- **Per feature**: confirm Integration and Documentation before considering the feature complete.

Tailor the list to the project once, then reuse it unchanged. A Definition of Done that is renegotiated every sprint is not a Definition of Done.

## Red Flags

- "It's done, I just haven't run it yet": unverified work is not done.
- "Tests pass" used as a synonym for done while docs, regressions, or runtime verification are skipped.
- A different bar applied depending on deadline pressure.
- Acceptance criteria treated as the whole bar, with no standing quality floor.
- "Done" declared before human review on changes that need it.

## ⚠️ Fundamental Principle

**Fix content, not rules.** When files violate limits/standards:
- ✅ Reduce file size (split, compress, extract)
- ✅ Fix formatting issues
- ✅ Remove duplication
- ❌ NEVER change limits in *_standards.md
- ❌ NEVER relax rules to make violations pass

This is non-negotiable. Changing rules instead of fixing content is forbidden.

## 1. Hierarchy & Links

### Must Pass
- [ ] CLAUDE.md exists at project root
- [ ] CLAUDE.md links to all primary docs (README, docs/*)
- [ ] All docs in docs/ reachable from CLAUDE.md (max 2 hops)
- [ ] No broken internal links (404)
- [ ] No orphaned .md files (unreachable from CLAUDE.md)

### Should Pass
- [ ] Consistent link format (relative paths)
- [ ] Links use descriptive text (not "click here")
- [ ] Bidirectional links for related docs
- [ ] TOC in files >100 lines

## 2. Single Source of Truth (SSOT)

### Must Pass
- [ ] No identical paragraphs across files
- [ ] No copy-pasted sections
- [ ] Shared concepts defined in one place with links elsewhere
- [ ] Clear ownership: each concept has one authoritative source

### Should Pass
- [ ] Cross-references use links, not inline copies
- [ ] Definitions not repeated (link to glossary/source)
- [ ] Version numbers in one place only
- [ ] Config examples not duplicated

### Detection Patterns
- Same paragraph in multiple files
- Similar tables with same data
- Repeated code examples
- Same list items in different docs

## 3. Proactive Compression

**Goal:** Minimum viable size - smallest document that fully conveys information.
Size limits are upper bounds, NOT targets. A 100-line file instead of 300 = success!

### Must Pass
- [ ] **All files checked for compression** (even under-limit ones!)
- [ ] No filler words (simply, easily, basically, actually, really, very)
- [ ] No obvious statements ("This section describes...")
- [ ] No over-explanations (one concept = one sentence max)
- [ ] Comparisons converted to tables
- [ ] Enumerations converted to lists
- [ ] Active voice used (not passive)

### Compression Targets

| Content Type | Before | After | Technique |
|--------------|--------|-------|-----------|
| Comparison prose | "X is better than Y because..." | Table: X vs Y | prose→table |
| Long explanation | 5 sentences | 1-2 sentences | remove filler |
| Obvious statement | "This function does X" | (delete) | remove obvious |
| Repeated info | same info in 3 places | 1 place + links | SSOT |
| Verbose phrase | "in order to" | "to" | compress |

### Meaningless Content Patterns (DELETE)
- "This section describes/explains..."
- "As mentioned above/below..."
- "It is important to note that..."
- "Please note that..."
- "In this document, we will..."
- "The purpose of this is to..."

### Detection Patterns
- Verbose phrases (in order to → to, at this point → now)
- Long paragraphs (>3 sentences)
- Over-explained obvious concepts
- Prose comparisons: "X is better than Y", "compared to"
- Prose enumerations: "First..., Second...", "Additionally..."

## 4. Requirements Compliance

### Must Pass
- [ ] CLAUDE.md has: Repository section, Key Concepts, Important Details
- [ ] README.md has: About, Features, Installation, Usage
- [ ] SKILL.md has: YAML frontmatter (name, description), workflow, critical notes
- [ ] All docs end with single blank line (POSIX)
- [ ] **No code blocks in docs** - text descriptions only; code lives in codebase

### Should Pass
- [ ] Consistent heading hierarchy (h1 → h2 → h3)
- [ ] Tables properly formatted
- [ ] Callouts/admonitions for warnings

### No Code Policy

Documents describe algorithms and concepts in text, NOT code:
- ✅ "Function validates input, checks permissions, then processes request"
- ✅ "Loop iterates through items, filtering by status"
- ❌ `def process(item): ...` (code block)
- ❌ `for item in items: if item.status == 'active': ...`

**Exceptions:**
- CLI commands for installation/usage in README.md
- Config file snippets (YAML/JSON) when documenting configuration
- Shell commands for Quick Audit section

**Detection:** Search for triple backticks (```) with language tags (python, js, ts, etc.)

### Document-Specific Checks

| Document | Required Sections |
|----------|-------------------|
| CLAUDE.md | Repository, Key Concepts, Important Details |
| README.md | About, Features, Installation, Usage, License |
| SKILL.md | Frontmatter, Purpose, Workflow, Critical Notes, Version |
| Guide | Purpose, Steps, Examples, Troubleshooting |
| ADR | Context, Decision, Consequences |

**False positive filtering (Layer 2 reasoning):**
- Template placeholders (`{placeholder}`, `YOUR_*`, `<project>`, `xxx`) -> skip
- Example/hypothetical paths (preceded by "e.g.", "for example", "such as") -> skip
- Future-tense claims ("will add", "planned", "TODO") -> skip or LOW
- Conditional claims ("if using X, configure Y") -> verify only if X detected in tech_stack
- External service paths (URLs, external repos) -> skip
- Paths in SCOPE/comment HTML blocks describing other projects -> skip
- `.env.example` values -> skip (expected to differ from actual)
