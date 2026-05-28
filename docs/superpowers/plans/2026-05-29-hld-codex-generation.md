# HLD-CODEX Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a new `HLD-CODEX` folder with 116 complete system-design solution files, reusing Claude's 11 existing solution files where available and generating the remaining files in the same solution-oriented structure.

**Architecture:** Use `HLD-Problems` as the full source of truth for problem coverage and source content. Map Claude's existing `HLD-Solutions` files by leading problem number and copy those contents unchanged into the target path matching the original problem-bank filename. For the remaining files, transform the existing deep-dive content into a Claude-style solution layout with concrete sections, diagrams, flows, observability, trade-offs, and interview talking points.

**Tech Stack:** Markdown, Python standard library for deterministic corpus generation, shell verification commands.

---

### Task 1: Generate The Corpus

**Files:**
- Create: `HLD-CODEX/`
- Read: `HLD-Problems/**/*.md`
- Read: `HLD-Solutions/**/*.md`

- [ ] **Step 1: Copy README/category scaffolding**

Create `HLD-CODEX`, copy root/category READMEs from `HLD-Problems`, and adjust the root title to describe the generated Codex solution set.

- [ ] **Step 2: Reuse Claude files by problem number**

For each file in `HLD-Solutions`, detect the three-digit prefix and copy the file body into the matching `HLD-CODEX` path derived from `HLD-Problems`.

- [ ] **Step 3: Transform remaining files**

For every problem file without a Claude solution, read the existing problem content and reshape it into these sections:

```markdown
# <Problem Title> - Complete System Design
## 1. Functional Requirements
## 2. Non-Functional Requirements
## 3. Capacity Estimation
## 4. Data Modeling
## 5. High-Level Design (HLD)
## 6. Low-Level Design (LLD)
## 7. Architecture Components
## 8. Deep Dive of Each Component/Service
## 9. Component Optimization
## 10. Observability
## 11. Considerations & Assumptions
## Summary: Interview Talking Points
```

Preserve useful API contracts, events, diagrams, schemas, state machines, scaling bottlenecks, security notes, cost models, and whiteboard structures from the source content.

### Task 2: Validate Output

**Files:**
- Read: `HLD-CODEX/**/*.md`

- [ ] **Step 1: Verify problem count**

Run:

```bash
find HLD-CODEX -type f -name '*.md' ! -name 'README.md' | sort | wc -l
```

Expected output: `116`.

- [ ] **Step 2: Verify Claude reuse**

Compare known reused files against their source bodies with `cmp` after accounting for target filename differences. Expected: reused file contents match exactly.

- [ ] **Step 3: Verify required section coverage**

Check that every non-README problem file contains the core solution markers:

```text
Complete System Design
Functional Requirements
Non-Functional Requirements
Capacity Estimation
High-Level Design
Observability
Interview Talking Points
```

- [ ] **Step 4: Spot-check representative files**

Open at least one reused Claude file and several generated files from different categories to confirm the generated structure is readable and not empty.
