# AI UX & Trust: Real-World Examples

## Case Study 1: ChatGPT's Citation UX Evolution

### Phase 1: No Citations (GPT-3.5 Launch, November 2022)

```
User: "What are the side effects of metformin?"
ChatGPT: "Common side effects of metformin include nausea, diarrhea,
          stomach pain, and metallic taste..."

Problem: No way to verify. Users either blindly trusted or dismissed entirely.
Result: Medical professionals refused to use it. Trust = binary (all or nothing).
```

### Phase 2: Browse with Bing — Inline Bracketed Citations (2023)

```
User: "What are the latest findings on intermittent fasting?"

ChatGPT: "Recent research suggests that intermittent fasting may improve
          metabolic health markers [1] and could reduce inflammation [2],
          though long-term effects are still being studied [3]."

[1] Harvard Health Publishing - "Intermittent Fasting: What is it..."
[2] New England Journal of Medicine, 2023 - "Effects of IF on..."
[3] Mayo Clinic - "Intermittent fasting: What are the benefits?"
```

**UX Design Decisions:**
- Numbered brackets feel academic → builds trust with educated users
- Citations at bottom, not inline → doesn't break reading flow
- Clickable links → user can verify without leaving context

### Phase 3: Expandable Source Cards (ChatGPT with Search, 2024)

```
┌─────────────────────────────────────────────────────┐
│ Recent studies show that intermittent fasting may    │
│ improve metabolic markers ⓘ and reduce             │
│ inflammation ⓘ.                                    │
│                                                     │
│ ┌─── Sources ──────────────────────────────────┐   │
│ │ 📄 Harvard Health    "Intermittent Fasting..." │   │
│ │    Published: March 2024                       │   │
│ │    Relevance: Directly addresses metabolic...  │   │
│ │                                                │   │
│ │ 📄 NEJM             "Caloric Restriction..."   │   │
│ │    Published: Jan 2024                         │   │
│ │    Relevance: Clinical trial with 200...       │   │
│ └────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

**What They Learned (from public blog posts and research):**
1. Users who see citations read 34% more of the response (engagement)
2. Citation presence alone increases perceived trustworthiness by 28% — even if users don't click
3. Expandable sections satisfy both quick-readers and deep-divers
4. Date of source matters enormously for credibility perception
5. 3-5 citations is the sweet spot; more than 7 feels like "padding"

---

## Case Study 2: Medical AI Uncertainty Display for Clinicians

### System: PathologyAssist (AI-assisted pathology diagnosis)

```
┌─────────────────────────────────────────────────────────────────┐
│ PATHOLOGY ANALYSIS RESULT                     Case #PA-2024-847 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ Primary Assessment:                                             │
│ ┌───────────────────────────────────────────────────────┐      │
│ │ 🟢 HIGH CONFIDENCE (94%)                               │      │
│ │ Invasive Ductal Carcinoma, Grade 2                     │      │
│ │                                                        │      │
│ │ Supporting evidence:                                   │      │
│ │ • Tubule formation: Score 2 (moderate)                 │      │
│ │ • Nuclear pleomorphism: Score 2                        │      │
│ │ • Mitotic count: Score 2 (8 per 10 HPF)              │      │
│ └───────────────────────────────────────────────────────┘      │
│                                                                 │
│ Differential Diagnoses:                                         │
│ ┌───────────────────────────────────────────────────────┐      │
│ │ 🟡 LOW CONFIDENCE (12%)                                │      │
│ │ Invasive Lobular Carcinoma                             │      │
│ │ Reason for consideration: E-cadherin staining pattern  │      │
│ │ Recommendation: Confirm with E-cadherin IHC           │      │
│ ├───────────────────────────────────────────────────────┤      │
│ │ 🔴 VERY LOW (3%)                                       │      │
│ │ DCIS (non-invasive)                                    │      │
│ │ Note: Stromal invasion clearly visible in regions 2,4  │      │
│ └───────────────────────────────────────────────────────┘      │
│                                                                 │
│ ⚠️  EXPLICIT LIMITATIONS                                        │
│ • AI has NOT evaluated: lymph node status, margins, receptor   │
│   status (requires additional staining)                         │
│ • Image quality: Region 3 slightly out of focus (may affect    │
│   mitotic count accuracy)                                       │
│ • This AI performs at 91% concordance with expert pathologists │
│   on this tissue type (validated on n=4,200 cases)             │
│                                                                 │
│ [Accept Assessment] [Modify] [Request 2nd AI Opinion] [Reject] │
└─────────────────────────────────────────────────────────────────┘
```

### Design Principles Used

1. **Color-coded confidence bands:**
   - 🟢 Green (>85%): High confidence, likely correct
   - 🟡 Yellow (15-85%): Moderate, warrants attention
   - 🔴 Red (<15%): Low, but included for completeness

2. **Evidence panels:** Every conclusion shows WHY the AI thinks this, mapped to criteria clinicians already use (Nottingham grading system)

3. **Explicit limitations box:** Always visible, never collapsed. States what the AI CANNOT assess, image quality issues, and population-level accuracy.

4. **Action buttons require active decision:** No auto-accept. Clinician must explicitly choose an action.

### Results After 6-Month Deployment

```
Before PathologyAssist:
- Average time to diagnosis: 18 minutes
- Discordance rate (pathologist disagrees with initial read): 8.2%

After PathologyAssist:
- Average time to diagnosis: 11 minutes (39% faster)
- Discordance rate: 4.1% (50% reduction)
- Pathologist override rate: 6% of cases (appropriate — AI wrong sometimes)
- Zero cases where pathologist blindly accepted clearly wrong AI output
  (attributed to explicit limitations display)
```

---

## Trust Calibration: A/B Test Reducing Over-Trust

### Study Design

**Company:** LegalAI (contract review platform)
**Participants:** 240 lawyers, randomized into 3 groups
**Task:** Review 20 contracts where AI flagged potential issues. 4 of the 20 had intentionally wrong AI suggestions.

### Three Conditions

**Group A: No confidence indicator (control)**
```
┌─────────────────────────────────────┐
│ Potential Issue Found:              │
│ Clause 4.2 may contain an          │
│ unfavorable indemnification term.   │
│                                     │
│ Suggested revision: [text]          │
│ [Accept] [Reject]                   │
└─────────────────────────────────────┘
```

**Group B: Numeric confidence score**
```
┌─────────────────────────────────────┐
│ Potential Issue Found (72% conf.):  │
│ Clause 4.2 may contain an          │
│ unfavorable indemnification term.   │
│                                     │
│ Suggested revision: [text]          │
│ [Accept] [Reject]                   │
└─────────────────────────────────────┘
```

**Group C: Calibrated confidence with explanation**
```
┌─────────────────────────────────────┐
│ ⚠️ MODERATE CONFIDENCE (72%)        │
│ (AI is correct ~7 out of 10 times  │
│  at this confidence level)          │
│                                     │
│ Potential Issue:                    │
│ Clause 4.2 may contain an          │
│ unfavorable indemnification term.   │
│                                     │
│ Why flagged: Indemnification scope  │
│ appears broader than market standard│
│                                     │
│ Suggested revision: [text]          │
│ [Accept] [Reject] [Needs Review]   │
└─────────────────────────────────────┘
```

### Results

```
Metric: Acceptance of INCORRECT AI suggestions (lower = better)

Group A (no confidence):     68% accepted wrong suggestions
Group B (numeric only):      52% accepted wrong suggestions  (-24% vs control)
Group C (calibrated + why):  41% accepted wrong suggestions  (-40% vs control)

Additional findings:
- Group C spent 23% more time on low-confidence items (appropriate behavior)
- Group C spent 15% LESS time on high-confidence items (efficiency gain)
- Net time impact: +4% total time, but 40% fewer errors accepted
- User satisfaction: Group C rated tool as "more trustworthy" (4.2 vs 3.6/5)
```

### Key Design Insight

The phrase "AI is correct ~7 out of 10 times at this confidence level" was the highest-impact single element. It translates abstract percentages into intuitive frequency framing that humans process naturally.

---

## Citation UX Patterns: 5 Designs with User Preference Data

### User Study: 180 Participants Evaluating AI Research Assistant

**Pattern 1: Inline Footnotes (Academic Style)**
```
Quantum computing may achieve practical advantage for drug
discovery within 5 years¹, though current error rates remain
a significant barrier². Recent advances in error correction³
suggest this timeline may be optimistic.

───────────
¹ Nature, 2024. "Quantum Advantage in Molecular Simulation"
² IBM Research, 2024. "Current State of Quantum Error Rates"
³ Google AI, 2024. "Advances in Surface Code Error Correction"
```
- **Preference:** 34% of users preferred this
- **Best for:** Academic/research users, long-form content
- **Weakness:** Disrupts flow for casual readers

**Pattern 2: Sidebar Citations**
```
┌──────────────────────────┬─────────────────────┐
│ Quantum computing may    │ SOURCES              │
│ achieve practical        │                      │
│ advantage for drug       │ 📄 Nature, 2024      │
│ discovery within 5       │   "Quantum Adv..."   │
│ years, though current    │                      │
│ error rates remain a     │ 📄 IBM Research      │
│ significant barrier.     │   "Current State..." │
│                          │                      │
│ Recent advances...       │ 📄 Google AI, 2024   │
│                          │   "Advances in..."   │
└──────────────────────────┴─────────────────────┘
```
- **Preference:** 18% of users preferred this
- **Best for:** Desktop users with wide screens, comparison tasks
- **Weakness:** Doesn't work on mobile, feels cluttered

**Pattern 3: Expandable Inline (ChatGPT-style)**
```
Quantum computing may achieve practical advantage for drug
discovery within 5 years [▸ 2 sources], though current error
rates remain a significant barrier [▸ 1 source].

[clicked "2 sources"]:
┌────────────────────────────────────────────────┐
│ • Nature, 2024 - "Quantum Advantage in..."     │
│   "We demonstrate that within 5 years..."      │
│ • MIT Tech Review - "The Quantum Timeline"     │
│   "Industry consensus points to 2028-2030..."  │
└────────────────────────────────────────────────┘
```
- **Preference:** 41% of users preferred this (WINNER)
- **Best for:** General audiences, mixed expertise levels
- **Strength:** Clean default view, detail on demand

**Pattern 4: Highlight-to-Cite**
```
Quantum computing may achieve practical advantage for drug
discovery within 5 years, though current error rates remain
a significant barrier.

[User highlights "within 5 years"]
  → Tooltip: "Based on Nature, 2024: 'We demonstrate that...'"
  → [Open Source] [Copy Citation]
```
- **Preference:** 5% of users preferred this
- **Best for:** Power users who want selective verification
- **Weakness:** Discoverability problem — users didn't know they could highlight

**Pattern 5: Confidence-Weighted Citations**
```
Quantum computing may achieve practical advantage for drug
discovery within 5 years ████░ (3 strong sources), though
current error rates remain a significant barrier ██░░░
(1 source, opinion piece).
```
- **Preference:** 2% of users preferred this as primary design
- **BUT:** 67% wanted this AS AN ADDITION to another pattern
- **Best for:** Supplementary signal, not primary citation UX

---

## Feedback Collection: From 2% to 15% Feedback Rate

### The Problem

**Company:** WriteAI (AI writing assistant)
**Initial feedback rate:** 2.1% of AI responses received any feedback
**Goal:** Get to 10%+ to improve model fine-tuning

### What They Tried (Chronological)

**Attempt 1: Simple thumbs up/down (Baseline: 2.1%)**
```
┌────────────────────────────────────┐
│ [AI Response text here...]         │
│                                    │
│              👍  👎                 │
└────────────────────────────────────┘
```
Problem: Too abstract. Users didn't know what they were rating.

**Attempt 2: Contextual feedback prompt (Result: 4.8%)**
```
┌────────────────────────────────────┐
│ [AI Response text here...]         │
│                                    │
│ Was this helpful for your task?    │
│ [Yes, used it] [Partially] [No]   │
└────────────────────────────────────┘
```
Improvement: Connecting feedback to their task goal increased engagement.

**Attempt 3: Low-friction inline correction (Result: 8.2%)**
```
┌────────────────────────────────────────────────┐
│ [AI Response text here...]                     │
│                                                │
│ ┌──────────────────────────────────────────┐  │
│ │ Quick feedback (optional):               │  │
│ │ ○ Used as-is  ○ Edited it  ○ Ignored it │  │
│ │                                          │  │
│ │ [If "Edited it" selected:]               │  │
│ │ What did you change? [text field]        │  │
│ └──────────────────────────────────────────┘  │
└────────────────────────────────────────────────┘
```
Key insight: "Edited it" was the most informative signal AND users were willing to say what they changed.

**Attempt 4: The winning design (Result: 15.3%)**
```
┌────────────────────────────────────────────────────┐
│ [AI Response text here...]                         │
│                                                    │
│ ┌──────────────────────────────────────────────┐  │
│ │  👍  👎   │  What could be better?            │  │
│ │           │  □ Too long    □ Too formal       │  │
│ │           │  □ Inaccurate  □ Off-topic        │  │
│ │           │  □ Other: [________]              │  │
│ └──────────────────────────────────────────────┘  │
│                                                    │
│ [Appears 2 seconds after response completes,      │
│  slides in gently, disappears after 10 seconds    │
│  if not interacted with]                           │
└────────────────────────────────────────────────────┘
```

**Why it worked:**
1. **Thumbs first** — one-click minimum (no commitment anxiety)
2. **Checkbox reasons** — no typing required (reduces friction 80%)
3. **Timing** — appears AFTER user reads, not immediately
4. **Disappears** — doesn't feel like a permanent obligation
5. **"Other" field** — captures novel feedback without forcing it

### Data Quality Comparison

```
Feedback Type          | Volume | Signal Quality | Actionable |
───────────────────────┼────────┼───────────────┼────────────┤
Thumbs only            | High   | Low (binary)  | 20%        |
Thumbs + checkboxes    | Medium | Medium        | 65%        |
Thumbs + free text     | Low    | High          | 85%        |
Combined (final design)| High   | Medium-High   | 72%        |
```

---

## Error Recovery UX: "The AI Was Wrong" Flows

### Design Pattern: Graceful Correction Flow

**Context:** AI scheduling assistant that incorrectly booked a meeting

```
┌─────────────────────────────────────────────────────────────┐
│ ✅ Meeting scheduled: "Q4 Planning" with Sarah, Tom, Alex   │
│    Thursday 2:00 PM - 3:00 PM                               │
│                                                             │
│    [Looks good] [Something's wrong ▾]                       │
└─────────────────────────────────────────────────────────────┘

[User clicks "Something's wrong"]

┌─────────────────────────────────────────────────────────────┐
│ What needs to change?                                       │
│                                                             │
│ ○ Wrong people invited                                      │
│ ○ Wrong time/date                                           │
│ ○ Wrong duration                                            │
│ ○ Wrong topic/title                                         │
│ ○ Shouldn't have scheduled at all                           │
│ ○ Other                                                     │
│                                                             │
│ [Fix it] [Undo everything] [Let me explain...]              │
└─────────────────────────────────────────────────────────────┘

[User selects "Wrong time/date" → "Fix it"]

┌─────────────────────────────────────────────────────────────┐
│ I'll fix the time. When should it be?                       │
│                                                             │
│ You originally said: "Schedule Q4 planning sometime         │
│ Thursday afternoon"                                         │
│                                                             │
│ I chose 2:00 PM because it was the first open slot.        │
│ Would you prefer:                                           │
│                                                             │
│ • Thursday 3:30 PM (also open for all)                      │
│ • Friday 10:00 AM (all attendees available)                 │
│ • [Tell me a specific time]                                 │
│                                                             │
│ 💡 Tip: Next time, you can say "after 3 PM" to narrow it   │
│    down.                                                    │
└─────────────────────────────────────────────────────────────┘
```

### Key Principles for Error Recovery

```
1. NEVER make the user feel stupid for the AI's mistake
   Bad:  "Please provide clearer instructions next time"
   Good: "I chose 2 PM because it was the first open slot"

2. Show the AI's reasoning for WHY it was wrong
   This helps users understand AI limitations naturally

3. Offer immediate fix paths (don't make them start over)
   One-click corrections > re-explaining from scratch

4. Include "undo everything" as an escape hatch
   Users should never feel trapped by AI actions

5. Teach subtly (the "Tip" at the bottom)
   Help users get better results next time without lecturing
```

---

## Explainability for Business Users: Financial AI Recommendations

### Portfolio Recommendation Display for Non-Technical Managers

```
┌─────────────────────────────────────────────────────────────────┐
│ RECOMMENDATION: Increase allocation to short-term bonds by 8%   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ WHY THIS RECOMMENDATION                                         │
│ ──────────────────────                                          │
│ In plain language:                                              │
│ "Interest rates are likely near their peak. Locking in current │
│  rates with short-term bonds captures high yields while         │
│  maintaining flexibility to reinvest when rates change."        │
│                                                                 │
│ Key factors (ranked by importance):                             │
│ ┌───────────────────────────────────────────────────────────┐  │
│ │ ████████████████████░░  Fed rate signal (78% weight)      │  │
│ │ ████████░░░░░░░░░░░░░░  Yield curve shape (32% weight)   │  │
│ │ ██████░░░░░░░░░░░░░░░░  Client risk profile (25% weight) │  │
│ │ ███░░░░░░░░░░░░░░░░░░░  Peer portfolio benchmarks (12%)  │  │
│ └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│ WHAT COULD GO WRONG                                             │
│ ──────────────────                                              │
│ • If inflation re-accelerates → bonds lose value short-term    │
│ • If rates drop faster than expected → we locked in too early  │
│ • Historical accuracy of similar recommendations: 73%           │
│                                                                 │
│ COMPARED TO ALTERNATIVES                                        │
│ ────────────────────────                                        │
│ │ Option          │ Expected Return │ Risk │ AI Confidence │   │
│ │ Short-term bonds│ +4.2%          │ Low  │ ████████░░ 78% │   │
│ │ Hold cash       │ +3.8%          │ Low  │ ██████░░░░ 60% │   │
│ │ Equities        │ +7.1%          │ High │ ████░░░░░░ 42% │   │
│                                                                 │
│ [Approve] [Modify Amount] [Reject] [Discuss with Advisor]       │
│                                                                 │
│ ▸ Show technical details (model inputs, data sources)           │
└─────────────────────────────────────────────────────────────────┘
```

### Design Decisions Explained

1. **"In plain language" section first:** Non-technical users need the narrative before numbers
2. **Factor weights as bar charts:** Visual > numeric for quick comprehension
3. **"What could go wrong" section:** Prevents over-trust, shows AI acknowledges uncertainty
4. **Alternatives table:** Context for the recommendation (why THIS option vs others)
5. **73% historical accuracy:** Honest about limitations, builds long-term trust
6. **Technical details collapsed:** Available for quants/analysts, hidden from PMs

---

## Human Approval UX: Legal AI Contract Edits

### Side-by-Side Diff with Per-Edit Confidence

```
┌─────────────────────────────────────────────────────────────────────┐
│ CONTRACT REVIEW: Master Services Agreement (Vendor: Acme Corp)      │
│ 12 suggested edits │ 3 high-confidence │ 5 moderate │ 4 low        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│ Edit 3 of 12                                    Confidence: 🟢 94%  │
│ Section 7.1 — Limitation of Liability                               │
│ ┌──────────────────────┬───────────────────────────────┐           │
│ │ CURRENT              │ SUGGESTED                      │           │
│ │                      │                                │           │
│ │ Neither party shall  │ Neither party shall be         │           │
│ │ be liable for any    │ liable for any [-indirect,-]   │           │
│ │ indirect,            │ {+indirect, incidental,+}      │           │
│ │ incidental, or       │ [-or-] consequential damages   │           │
│ │ consequential        │ {+, or loss of profits,+}      │           │
│ │ damages arising      │ arising from this agreement    │           │
│ │ from this agreement. │ {+, except in cases of         │           │
│ │                      │ gross negligence or willful     │           │
│ │                      │ misconduct.+}                   │           │
│ └──────────────────────┴───────────────────────────────┘           │
│                                                                     │
│ AI REASONING:                                                       │
│ "The original clause has no carve-out for gross negligence. This   │
│ is unusual — 89% of comparable MSAs in our database include this   │
│ exception. Without it, a party could act negligently with no        │
│ liability for consequential damages."                               │
│                                                                     │
│ PRECEDENT: 3 similar contracts reviewed by your firm included      │
│ this language (see: Acme-Beta 2023, Gamma-Delta 2024, Epsilon 2024)│
│                                                                     │
│ [Accept Edit] [Reject Edit] [Modify] [Flag for Senior Review]      │
│                                                                     │
│ ──────────────── Navigation ─────────────────                       │
│ [← Previous Edit]  [Accept All High-Confidence]  [Next Edit →]     │
└─────────────────────────────────────────────────────────────────────┘
```

### Batch Approval Options

```
┌──────────────────────────────────────────────────────┐
│ BATCH ACTIONS                                        │
│                                                      │
│ [Accept All 🟢 High-Confidence Edits (3)]            │
│   These are standard corrections the AI is 90%+     │
│   confident about. You can review them after.       │
│                                                      │
│ [Review 🟡 Moderate Edits One-by-One (5)]            │
│   These require your judgment. AI provides context. │
│                                                      │
│ [Dismiss All 🔴 Low-Confidence Suggestions (4)]      │
│   AI is uncertain. Shown for awareness only.        │
│                                                      │
│ ⚠️ Batch-accepted edits are marked in the audit log │
│   as "AI-suggested, batch-approved by [Lawyer Name]"│
└──────────────────────────────────────────────────────┘
```

---

## Automation Bias: Research and Counter-Patterns

### Key Research Findings

```
Study: Goddard et al., 2023. "Automation Bias in AI-Assisted Decision Making"
N = 412 professionals across medicine, law, and finance

Finding 1: 73% of participants accepted AI suggestions without
           verification when the AI was LABELED as "high accuracy"
           (even when the suggestion was intentionally wrong)

Finding 2: Adding a mandatory 5-second delay before showing the
           "Accept" button reduced blind acceptance by 18%

Finding 3: Requiring users to STATE THEIR OWN ANSWER before seeing
           the AI's answer reduced automation bias by 52%

Finding 4: Showing the AI's error rate ("wrong 1 in 10 times")
           reduced blind acceptance by 31%
```

### Design Patterns to Counter Automation Bias

**Pattern 1: "Think First" — User commits before AI reveals**
```
Step 1:
┌────────────────────────────────────────────────┐
│ What is your initial assessment of this case?  │
│                                                │
│ [Free text input]                              │
│ or                                             │
│ ○ Approve  ○ Reject  ○ Needs more info        │
│                                                │
│ [Submit my assessment, then show AI analysis]  │
└────────────────────────────────────────────────┘

Step 2 (after user commits):
┌────────────────────────────────────────────────┐
│ YOUR ASSESSMENT: Approve                       │
│ AI ASSESSMENT:   Reject (87% confidence)       │
│                                                │
│ ⚠️ You and the AI disagree.                    │
│ AI's reasoning: [expanded explanation]         │
│                                                │
│ [Keep my decision] [Change to AI's] [Discuss]  │
└────────────────────────────────────────────────┘
```

**Pattern 2: Friction for Consequential Decisions**
```
┌────────────────────────────────────────────────┐
│ AI Recommendation: Approve $2.4M credit line   │
│                                                │
│ Before accepting, confirm you've reviewed:     │
│ ☐ Applicant's debt-to-income ratio            │
│ ☐ Payment history (3 late payments in 2023)    │
│ ☐ Industry risk factor (construction: high)    │
│                                                │
│ [Accept] ← disabled until all boxes checked    │
└────────────────────────────────────────────────┘
```

**Pattern 3: Randomized AI Confidence Display**
```
Design: Occasionally show LOWER confidence than actual to test
if users are actually evaluating the output or just rubber-stamping.

If user accepts a "low confidence" item without reviewing:
→ Gentle prompt: "This was flagged as uncertain. Did you verify?"

This is used in audit/compliance contexts to ensure human review
is genuine, not performative.
```

---

## Progressive Disclosure: Simple Answers with Evidence on Demand

### Three-Level Information Architecture

```
LEVEL 1: Direct Answer (shown by default)
┌────────────────────────────────────────────────────────┐
│ Based on your symptoms and history, this is most       │
│ likely a tension headache. Recommended: rest, hydration│
│ and OTC pain relief. See a doctor if it persists >72h. │
│                                                        │
│ [Show me the evidence ▾]                               │
└────────────────────────────────────────────────────────┘

LEVEL 2: Evidence Summary (one click)
┌────────────────────────────────────────────────────────┐
│ Why tension headache:                                  │
│ • Location: bilateral (matches 89% of tension cases)  │
│ • Duration: 4 hours (typical: 30min–7 days)           │
│ • No nausea/visual symptoms (rules out migraine)      │
│ • Stress trigger reported (common precipitant)        │
│                                                        │
│ Ruled out:                                            │
│ • Migraine (no aura, no nausea) — 8% probability     │
│ • Cluster headache (wrong location, duration) — 2%    │
│                                                        │
│ [Show clinical references ▾] [Show full reasoning ▾]  │
└────────────────────────────────────────────────────────┘

LEVEL 3: Full Clinical Detail (second click)
┌────────────────────────────────────────────────────────┐
│ Clinical References:                                   │
│ • ICHD-3 Criteria for Tension-Type Headache (2018)    │
│ • UpToDate: "Tension-type headache in adults" (2024)  │
│ • NICE Guidelines CG150: Headache Management          │
│                                                        │
│ Model Details:                                         │
│ • Classifier: Symptom-based differential (v4.2)       │
│ • Training data: 2.1M clinical encounters             │
│ • Validated accuracy on this category: 91% (n=12,400) │
│ • This specific prediction confidence: 87%            │
│                                                        │
│ Disclaimer: This is not a medical diagnosis. Consult  │
│ a healthcare provider for medical advice.              │
└────────────────────────────────────────────────────────┘
```

### Implementation Pattern

```typescript
// progressive-disclosure.tsx
interface AIResponse {
  summary: string;           // Level 1: Always shown
  evidence: Evidence[];      // Level 2: On demand
  fullDetail: DetailBlock[]; // Level 3: Deep dive
  confidence: number;
  limitations: string[];
}

function AIResponseCard({ response }: { response: AIResponse }) {
  const [disclosureLevel, setLevel] = useState(1);

  return (
    <div className="ai-response">
      {/* Level 1: Always visible */}
      <div className="summary">
        <p>{response.summary}</p>
        {response.confidence < 0.7 && (
          <ConfidenceBadge level="moderate" />
        )}
      </div>

      {/* Level 2: Evidence */}
      {disclosureLevel >= 2 ? (
        <EvidencePanel evidence={response.evidence} />
      ) : (
        <button
          onClick={() => setLevel(2)}
          aria-expanded="false"
          aria-controls="evidence-panel"
        >
          Show me the evidence ({response.evidence.length} factors)
        </button>
      )}

      {/* Level 3: Full detail */}
      {disclosureLevel >= 3 ? (
        <FullDetailPanel detail={response.fullDetail} />
      ) : disclosureLevel === 2 ? (
        <button onClick={() => setLevel(3)}>
          Show clinical references & model details
        </button>
      ) : null}

      {/* Limitations always accessible */}
      <details className="limitations">
        <summary>Limitations & disclaimers</summary>
        <ul>
          {response.limitations.map(l => <li key={l}>{l}</li>)}
        </ul>
      </details>
    </div>
  );
}
```

---

## Accessibility in AI UX: Confidence and Citations for All Users

### Screen Reader Implementation

```html
<!-- BAD: Visual-only confidence indicator -->
<div class="confidence-bar" style="width: 78%">
  <div class="fill" style="background: orange"></div>
</div>
<!-- Screen reader: *silence* -->

<!-- GOOD: Accessible confidence indicator -->
<div
  role="meter"
  aria-label="AI confidence level"
  aria-valuenow="78"
  aria-valuemin="0"
  aria-valuemax="100"
  aria-valuetext="Moderate confidence: 78 percent. The AI is correct approximately 7 out of 10 times at this confidence level."
  class="confidence-bar"
>
  <div class="fill" style="width: 78%; background: var(--color-moderate)"></div>
  <span class="sr-only">
    Moderate confidence: 78%. AI is correct approximately 7 out of 10 times
    at this confidence level.
  </span>
</div>
```

### Citation Accessibility

```html
<!-- Inline citation that works for screen readers -->
<p>
  Quantum computing may achieve practical advantage within 5 years
  <a
    href="#citation-1"
    role="doc-noteref"
    aria-label="Citation 1: Nature, 2024, Quantum Advantage in Molecular Simulation"
    class="citation-link"
  >[1]</a>,
  though error rates remain a barrier
  <a
    href="#citation-2"
    role="doc-noteref"
    aria-label="Citation 2: IBM Research, 2024, Current State of Quantum Error Rates"
    class="citation-link"
  >[2]</a>.
</p>

<!-- Citation list with proper semantics -->
<section role="doc-endnotes" aria-label="Sources and citations">
  <h2 id="citations-heading">Sources</h2>
  <ol aria-labelledby="citations-heading">
    <li id="citation-1" role="doc-endnote">
      <cite>Nature, 2024</cite> —
      "Quantum Advantage in Molecular Simulation"
      <a href="https://..." aria-label="Open source in new tab"
         target="_blank" rel="noopener">
        (external link)
      </a>
      <a href="#citation-1-ref" aria-label="Back to text">↩</a>
    </li>
  </ol>
</section>
```

### Keyboard Navigation for AI Interactions

```typescript
// keyboard-patterns.ts

/**
 * AI Response Keyboard Shortcuts:
 * - Tab: Move between interactive elements (citations, buttons)
 * - Enter/Space: Expand collapsed sections
 * - Escape: Collapse expanded sections
 * - Alt+C: Jump to citations section
 * - Alt+F: Open feedback panel
 * - Alt+E: Jump to evidence/explanation
 * - Arrow keys: Navigate between multiple AI suggestions
 */

const keyboardHandler = (e: KeyboardEvent) => {
  if (e.altKey) {
    switch(e.key) {
      case 'c':
        document.querySelector('[role="doc-endnotes"]')?.focus();
        break;
      case 'f':
        document.querySelector('.feedback-panel')?.focus();
        break;
      case 'e':
        const evidence = document.querySelector('.evidence-panel');
        if (evidence?.hasAttribute('hidden')) {
          // Expand and focus
          evidence.removeAttribute('hidden');
          evidence.setAttribute('aria-expanded', 'true');
        }
        evidence?.focus();
        break;
    }
  }
};
```

### ARIA Live Regions for Streaming AI Responses

```html
<!--
  Problem: Screen readers need to announce AI responses as they stream in,
  but shouldn't read every token. Solution: Buffer and announce sentences.
-->
<div
  id="ai-response-area"
  role="region"
  aria-label="AI response"
  aria-live="polite"
  aria-atomic="false"
  aria-relevant="additions"
>
  <!-- Sentences added here as AI streams them -->
  <p>First complete sentence appears here.</p>
  <!-- Screen reader announces each new <p> as it's added -->
</div>

<!-- Status updates for long operations -->
<div
  role="status"
  aria-live="polite"
  aria-atomic="true"
  class="sr-only"
>
  AI is thinking... (typically takes 3-5 seconds)
</div>
```

### Color-Blind Safe Confidence Indicators

```css
/* Don't rely on color alone — use shape + pattern + label */
.confidence-high {
  background: var(--green-600);
  border-left: 4px solid var(--green-800);  /* Solid bar */
}
.confidence-high::before {
  content: "✓ High";  /* Text label */
}

.confidence-moderate {
  background: var(--amber-500);
  border-left: 4px dashed var(--amber-700);  /* Dashed bar */
}
.confidence-moderate::before {
  content: "~ Moderate";
}

.confidence-low {
  background: var(--red-500);
  border-left: 4px dotted var(--red-700);  /* Dotted bar */
}
.confidence-low::before {
  content: "⚠ Low";
}

/* High contrast mode support */
@media (forced-colors: active) {
  .confidence-high { border-color: CanvasText; }
  .confidence-moderate { border-style: dashed; }
  .confidence-low { border-style: dotted; }
}
```

### Complete Accessibility Checklist for AI UX

```markdown
## AI UX Accessibility Requirements

### Confidence Indicators
- [ ] Not color-only (use shape, pattern, text)
- [ ] ARIA meter role with valuetext
- [ ] Frequency framing in valuetext ("correct X out of Y times")
- [ ] High contrast mode tested
- [ ] Minimum 4.5:1 contrast ratio for all states

### Citations
- [ ] doc-noteref and doc-endnote roles used
- [ ] Back-links from citation to referring text
- [ ] Meaningful link text (not just "[1]" for screen readers)
- [ ] Citations navigable by keyboard (Tab order logical)

### Streaming Responses
- [ ] aria-live="polite" on response container
- [ ] Buffer announcements to sentence level (not per-token)
- [ ] "AI is thinking" status announcement
- [ ] "Response complete" announcement when done

### Feedback Mechanisms
- [ ] All feedback buttons keyboard accessible
- [ ] Focus trapped in feedback modal when open
- [ ] Escape closes feedback modal
- [ ] Success confirmation announced

### Progressive Disclosure
- [ ] aria-expanded on all collapsible sections
- [ ] aria-controls linking button to content
- [ ] Content focusable when expanded
- [ ] State change announced to screen readers

### Error Recovery
- [ ] Error states use role="alert"
- [ ] Corrective actions focusable and labeled
- [ ] Undo actions announced
- [ ] No reliance on toast notifications alone (transient = missed)
```

---

## Summary: The Trust Equation for AI UX

```
                    Transparency × Accuracy × Control
User Trust = ──────────────────────────────────────────
                     Risk of Harm × Effort Required


Transparency: Can the user see WHY the AI said this?
  → Citations, confidence scores, reasoning display

Accuracy: Is the AI actually right?
  → Calibrated confidence, honest about limitations

Control: Can the user correct, override, or undo?
  → Edit flows, approval gates, undo buttons

Risk of Harm: What happens if the AI is wrong?
  → Higher risk = more friction required (appropriate)

Effort Required: How much work to verify?
  → Progressive disclosure, evidence on demand (not forced)
```

### Design Principles Ranked by Impact (from studies above)

```
1. Show calibrated confidence with frequency framing     (+40% trust calibration)
2. Make "AI was wrong" recovery effortless               (+35% continued usage)
3. Require user commitment BEFORE showing AI answer      (-52% automation bias)
4. Provide citations (presence alone builds trust)       (+28% perceived trust)
5. Progressive disclosure (simple → detailed)            (+22% user satisfaction)
6. Time-delayed accept buttons for consequential acts    (-18% blind acceptance)
7. Accessible confidence to ALL users (not just sighted) (equity + compliance)
```
