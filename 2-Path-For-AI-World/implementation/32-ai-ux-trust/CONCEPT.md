# AI UX and Human Trust

## Senior Principle

> **"The UI must teach the user how much to trust the AI."**

An AI system that is 80% accurate but presents itself as 100% confident is more dangerous than one that is 60% accurate but clearly communicates its uncertainty. The goal is not maximum trust — it is *calibrated* trust.

---

## 1. Trust Calibration

Trust calibration means users should trust AI **the right amount** — neither too much nor too little.

### The Trust Spectrum

```
Under-trust          Calibrated Trust         Over-trust
|--------------------|----|------------------|
User ignores         User verifies          User blindly
valid suggestions    appropriately          follows AI
```

### Why Miscalibration is Dangerous

| Problem | Symptom | Consequence |
|---------|---------|-------------|
| Over-trust (automation bias) | User accepts wrong answer without checking | Medical misdiagnosis, financial loss, legal liability |
| Under-trust | User ignores correct AI suggestions | Wasted investment, no productivity gain |
| Unstable trust | User doesn't know when to check | Inconsistent outcomes, user anxiety |

### How to Calibrate Trust

1. **Show accuracy history**: "This model is correct ~85% of the time for this task type"
2. **Show confidence per-response**: "High confidence" vs "I'm not sure about this"
3. **Validate predictions**: Show users when AI was right/wrong to build intuition
4. **Differentiate task types**: AI may be great at classification but poor at open-ended generation
5. **Provide comparison anchors**: "Expert humans are ~90% accurate on this task"

### Trust Calibration Metrics

- **Calibration score**: Correlation between stated confidence and actual accuracy
- **User reliance rate**: How often users accept AI suggestions without modification
- **Appropriate rejection rate**: Users correctly rejecting wrong AI outputs
- **Override accuracy**: When users override AI, are they right?

---

## 2. Uncertainty Display

### Principles

- Never hide uncertainty — surface it proportionally
- Use the user's mental model (not statistical jargon)
- Different uncertainty types need different displays

### Types of Uncertainty

| Type | Source | Display Strategy |
|------|--------|-----------------|
| **Epistemic** | Lack of training data | "I haven't seen many examples like this" |
| **Aleatoric** | Inherent randomness | "This could go either way" |
| **Model** | Architecture limitations | "This is outside my capabilities" |
| **Input** | Ambiguous query | "I'm interpreting your question as..." |
| **Temporal** | Outdated knowledge | "My information may be outdated (cutoff: X)" |

### Visual Uncertainty Indicators

```
HIGH CONFIDENCE (>90%)
████████████████████░  "I'm confident about this"
Solid colors, no caveats, direct language

MEDIUM CONFIDENCE (60-90%)
████████████████░░░░░  "This is likely correct, but verify..."
Slightly muted colors, caveat present

LOW CONFIDENCE (30-60%)
██████████░░░░░░░░░░░  "I'm not sure — here's my best guess"
Warning colors, prominent caveat, alternatives shown

VERY LOW CONFIDENCE (<30%)
████░░░░░░░░░░░░░░░░░  "I don't have enough information to answer reliably"
Red/orange, strong caveat, suggest alternatives
```

### Anti-Patterns

- **Fake precision**: "I'm 73.2% confident" — meaningless to users
- **Binary confidence**: Only "sure" or "not sure" — misses nuance
- **Hidden uncertainty**: Presenting uncertain answers in the same style as certain ones
- **Uncertainty fatigue**: Every response has disclaimers, user ignores them all

---

## 3. Citation UX

### Why Citations Matter

Citations serve three purposes:
1. **Verifiability**: Users can check the source
2. **Trust building**: Shows reasoning is grounded
3. **Attribution**: Respects original authors

### Citation Display Patterns

#### Inline Citations
```
The capital of Australia is Canberra [1], not Sydney as commonly believed [2].

Sources:
[1] Wikipedia: Australia — en.wikipedia.org/wiki/Australia (accessed 2024-01-15)
[2] Common Misconceptions — misconceptions.io/geography (accessed 2024-01-15)
```

#### Sidebar Citations
```
┌─────────────────────────────┐  ┌──────────────────┐
│ Answer text with highlighted │  │ Sources:         │
│ segments that map to sources │  │ • Source A (★★★) │
│ on the right panel.          │  │ • Source B (★★)  │
└─────────────────────────────┘  │ • Source C (★)   │
                                  └──────────────────┘
```

#### Confidence-Weighted Citations
```
🟢 Strong support (3+ sources agree): "The event occurred in 1969"
🟡 Moderate support (1-2 sources): "The estimated cost was $2M"
🔴 Weak/conflicting sources: "Reports disagree on the outcome"
```

### Citation Quality Indicators

- **Source recency**: How old is the source?
- **Source authority**: Peer-reviewed? Official docs? Blog?
- **Source relevance**: How directly does it support the claim?
- **Source agreement**: Do multiple sources confirm?

---

## 4. Confidence Explanation

Users need to understand not just *what* the confidence level is, but *why*.

### Explanation Templates

```
HIGH CONFIDENCE because:
✓ Multiple authoritative sources agree
✓ This is a well-documented factual question
✓ The answer is unambiguous

LOW CONFIDENCE because:
⚠ Limited source material available
⚠ Sources provide conflicting information
⚠ This requires subjective judgment
⚠ My training data may be outdated on this topic
```

### Confidence Factors to Surface

| Factor | User-Friendly Label | Example |
|--------|-------------------|---------|
| Source agreement | "Sources agree/disagree" | "3 of 4 sources confirm this" |
| Task familiarity | "Common/rare question type" | "I answer questions like this frequently" |
| Input clarity | "Clear/ambiguous question" | "Your question has multiple interpretations" |
| Knowledge recency | "Up-to-date/possibly outdated" | "This topic changes rapidly" |
| Reasoning complexity | "Straightforward/complex reasoning" | "This required several reasoning steps" |

---

## 5. Human Approval UX

### When to Request Approval

| Risk Level | Action Type | Approval Pattern |
|-----------|-------------|-----------------|
| **Critical** | Delete data, send emails, financial transactions | Explicit approval + confirmation |
| **High** | Modify configs, update records | Approval with preview |
| **Medium** | Create drafts, suggest edits | Edit-before-action |
| **Low** | Search, summarize, format | No approval needed |

### Approval Request Structure

```
┌─────────────────────────────────────────────┐
│ 🔔 Action Requires Your Approval            │
├─────────────────────────────────────────────┤
│                                             │
│ WHAT: Send email to 150 customers           │
│ WHY:  You requested campaign launch         │
│ RISK: Medium — emails cannot be unsent      │
│                                             │
│ PREVIEW:                                    │
│ ┌─────────────────────────────────────────┐ │
│ │ Subject: Your weekly digest...          │ │
│ │ Body: Hi {{name}}, here are your...     │ │
│ └─────────────────────────────────────────┘ │
│                                             │
│ [✓ Approve]  [✎ Edit First]  [✗ Reject]    │
│                                             │
│ ⏱ Auto-cancels in 24 hours if no response  │
└─────────────────────────────────────────────┘
```

### Key Principles

1. **State what will happen** — not just "Confirm action?"
2. **Show reversibility** — "This can/cannot be undone"
3. **Provide preview** — let users see the outcome before committing
4. **Offer edit option** — not just approve/reject
5. **Set timeout** — don't leave actions hanging indefinitely
6. **Batch intelligently** — don't ask 50 approvals for related actions

---

## 6. Edit-Before-Action UX

Let users modify AI-generated content before it takes effect.

### Pattern

```
AI generates → User reviews → User edits → User confirms → Action executes
```

### Implementation Guidelines

- **Highlight AI-generated parts** so users know what to review
- **Show diff from original** when AI modifies existing content
- **Provide inline editing** — don't make users copy-paste
- **Track user edits** — learn what users consistently change
- **Suggest but don't assume** — "I've drafted this, please review"

### Edit Affordances

```
┌─────────────────────────────────────────────────┐
│ Draft Email (AI-generated — please review)      │
├─────────────────────────────────────────────────┤
│                                                 │
│ Subject: [Quarterly Report - Q4 2024         ]  │  ← editable
│                                                 │
│ Body:                                           │
│ ┌─────────────────────────────────────────────┐ │
│ │ Hi team,                                    │ │  ← editable
│ │                                             │ │
│ │ Attached is the Q4 report showing 12%       │ │
│ │ growth in...                                │ │
│ └─────────────────────────────────────────────┘ │
│                                                 │
│ Attachments: report_q4.pdf ✓                    │
│                                                 │
│ [Send As-Is]  [Send After Review]  [Discard]    │
└─────────────────────────────────────────────────┘
```

---

## 7. Escalation UX

### When AI Should Escalate to Humans

- Confidence below threshold for the risk level
- User explicitly requests human help
- Regulatory requirement for human decision
- AI detects adversarial or unusual input
- Repeated user corrections suggest AI is failing

### Escalation Flow

```
┌─────────────────────────────────────────────┐
│ 🔄 Connecting you with a human specialist   │
├─────────────────────────────────────────────┤
│                                             │
│ REASON: This question requires expertise    │
│         beyond my capabilities              │
│                                             │
│ WHAT I'VE DONE SO FAR:                      │
│ • Searched 3 knowledge bases                │
│ • Found partial answer (shared below)       │
│ • Identified this as a legal question       │
│                                             │
│ CONTEXT BEING SHARED:                       │
│ • Your question                             │
│ • My partial findings                       │
│ • This conversation history                 │
│                                             │
│ ESTIMATED WAIT: ~5 minutes                  │
│                                             │
│ [Continue waiting]  [Leave message instead] │
└─────────────────────────────────────────────┘
```

### Principles

1. **Explain why** — don't just say "transferring"
2. **Share context** — human shouldn't re-ask everything
3. **Show partial work** — AI's findings so far are valuable
4. **Set expectations** — estimated wait time
5. **Offer alternatives** — async option if wait is long

---

## 8. Refusal and Abstention UX

### How to Say "I Don't Know"

The goal: Be honest without being useless.

### Refusal Taxonomy

| Type | Example | Good Response |
|------|---------|--------------|
| **Knowledge gap** | "What happened yesterday?" | "I don't have access to yesterday's events. Here's where you can check: [link]" |
| **Capability limit** | "Predict the stock price" | "I can't predict markets, but I can analyze historical patterns and summarize analyst views" |
| **Safety boundary** | "How to hack X" | "I can't help with that. If you're doing security testing, here's the ethical approach: [link]" |
| **Ambiguity** | Unclear question | "I could interpret this several ways. Did you mean A, B, or C?" |
| **Low confidence** | Complex judgment call | "I'm not confident enough to answer this reliably. Here's what I do know, and I'd suggest consulting [expert type]" |

### Anti-Patterns in Refusal

- **Brick wall refusal**: "I cannot help with that." (no alternatives)
- **Over-refusal**: Refusing benign requests due to surface-level pattern matching
- **Apologetic refusal**: "I'm so sorry, I really wish I could help..." (wastes space, annoying)
- **Hidden refusal**: Answering confidently when actually uncertain

### Good Refusal Formula

```
[What I can't do] + [Why briefly] + [What I CAN do or suggest instead]
```

---

## 9. Feedback Collection

### Feedback Types

| Type | Mechanism | Use Case |
|------|-----------|----------|
| **Binary** | 👍/👎 | Quick quality signal |
| **Correction** | Edit AI output | Training data for improvement |
| **Rating** | 1-5 stars | Satisfaction tracking |
| **Report** | Flag + category | Safety/quality issues |
| **Free text** | Comment box | Nuanced feedback |
| **Implicit** | User behavior | Did they use the answer? Copy it? Ignore it? |

### Feedback Timing

- **Immediate**: Right after AI response (thumbs up/down)
- **Post-task**: After completing a workflow ("How did this session go?")
- **Periodic**: Weekly/monthly satisfaction surveys
- **Triggered**: After detected failures or corrections

### Principles

1. **Low friction** — 1 click for basic feedback
2. **Optional depth** — allow but don't require explanation
3. **Non-intrusive** — don't interrupt flow
4. **Acknowledge** — "Thanks for the feedback" (briefly)
5. **Close the loop** — show users their feedback led to improvements

---

## 10. Error Recovery

### Error Categories and Recovery Patterns

| Error Type | Example | Recovery |
|-----------|---------|----------|
| **Transient** | API timeout | Auto-retry with status |
| **Input** | Malformed query | Suggest correction |
| **Capacity** | Rate limited | Queue with ETA |
| **Logic** | Wrong answer detected | Offer correction + explain |
| **System** | Service down | Graceful degradation + status page |

### Error Message Formula

```
[What happened] + [Why it matters to you] + [What you can do] + [What we're doing]
```

### Example

```
❌ BAD:  "Error 500: Internal Server Error"
✅ GOOD: "I couldn't complete your request because the document service 
          is temporarily unavailable. Your draft is saved. You can:
          • Try again in a few minutes
          • Continue with other tasks
          We're aware of the issue and working on it."
```

---

## 11. Audit Trail Visibility

### What Users Should See

```
┌─────────────────────────────────────────────────┐
│ 📋 What I did (Audit Trail)                     │
├─────────────────────────────────────────────────┤
│                                                 │
│ 10:03:01  Received your question                │
│ 10:03:02  Searched knowledge base (3 results)   │
│ 10:03:03  Retrieved document: "Policy v2.1"     │
│ 10:03:04  Generated answer from 2 sources       │
│ 10:03:05  Confidence check: 87% (high)          │
│ 10:03:05  Delivered response                    │
│                                                 │
│ [View full details]  [Export log]               │
└─────────────────────────────────────────────────┘
```

### Audit Levels

| Audience | Detail Level | Purpose |
|----------|-------------|---------|
| End user | Summary | Transparency, trust |
| Power user | Detailed steps | Debugging, verification |
| Admin | Full trace | Compliance, investigation |
| Auditor | Immutable log | Regulatory compliance |

---

## 12. Explainability for Non-Technical Users

### Principles

- Use **analogies** not algorithms
- Show **because** not **how**
- Use **concrete examples** not abstract descriptions
- Layer detail: summary → details → technical (progressive disclosure)

### Translation Examples

| Technical | User-Friendly |
|-----------|--------------|
| "cosine similarity 0.92" | "Very closely related to your question" |
| "Retrieved 5 chunks from vector DB" | "Found 5 relevant sections in your documents" |
| "Temperature 0.7" | "Balanced between creative and precise" |
| "Top-k sampling, k=40" | "Considered 40 possible next words" |
| "Hallucination detected by grounding check" | "This claim isn't supported by the sources I found" |

---

## 13. Avoiding Automation Bias

Automation bias: the tendency to over-rely on automated systems, even when they're wrong.

### Mitigation Strategies

1. **Require engagement**: Don't let users approve without reviewing
2. **Vary presentation**: Don't always present AI suggestion first
3. **Show alternatives**: Present multiple options, not just the "best"
4. **Historical accuracy**: "I've been right X% of the time on similar questions"
5. **Spot checks**: Occasionally ask users to verify even high-confidence answers
6. **Training**: Educate users on when AI tends to fail

### Design Interventions

- **Friction for high-stakes**: Extra confirmation step for irreversible actions
- **Delay before action**: Brief pause so users actually read the preview
- **Random verification**: "Just checking — did you review this before approving?"
- **Disagree option prominence**: Make "reject" as easy as "accept"

---

## 14. Avoiding False Authority

### The Problem

AI systems that use authoritative language for uncertain answers create dangerous over-trust.

### Signals of False Authority

- Stating opinions as facts
- Not qualifying uncertain claims
- Using overly formal/expert tone for speculative content
- Presenting one interpretation when multiple exist
- Not acknowledging limitations

### Mitigation

| Instead of | Use |
|-----------|-----|
| "The answer is X" | "Based on available sources, X appears correct" |
| "You should do X" | "One approach is X. Consider also Y and Z" |
| "This is safe" | "This appears safe based on [criteria], but verify with [authority]" |
| "Studies show X" | "A 2023 study by [Author] found X (sample size: N)" |

---

## 15. Safe Defaults

### Principle

When in doubt, the system should do the **least harmful** thing by default.

### Safe Default Examples

| Decision | Safe Default | Why |
|----------|-------------|-----|
| Confidence display | Show uncertainty | Prevents over-trust |
| Action execution | Require approval | Prevents unintended consequences |
| Data sharing | Minimize | Privacy protection |
| Response style | Hedged language | Prevents false authority |
| Error handling | Fail open to human | Human can recover |
| Scope of action | Narrowest interpretation | Prevents unintended scope |

---

## 16. UX Patterns Table

| # | Pattern | Use When | Key Principle | Risk if Missing |
|---|---------|----------|---------------|----------------|
| 1 | **Confidence Badge** | Every AI response | Show calibrated confidence visually | Users can't assess reliability |
| 2 | **Inline Citations** | Factual claims | Link claims to sources | Users can't verify, trust erodes |
| 3 | **Action Preview** | Before any side-effect | Show what will happen | Unintended consequences |
| 4 | **Progressive Disclosure** | Complex explanations | Summary → Detail → Technical | Information overload |
| 5 | **Graceful Degradation** | System errors/limits | Partial value > total failure | User abandonment |
| 6 | **Feedback Micro-interaction** | After each AI output | 1-click signal with optional depth | No improvement signal |
| 7 | **Escalation Bridge** | AI confidence < threshold | Smooth handoff with context | User stuck, frustrated |
| 8 | **Audit Timeline** | Post-interaction review | Chronological action log | No accountability, no debugging |

---

## Summary

Building trustworthy AI UX is not about making AI seem more capable — it's about helping users develop **accurate mental models** of what AI can and cannot do. The best AI UX is one where users naturally calibrate their trust, verify when appropriate, and feel empowered rather than dependent.
