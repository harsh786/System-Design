#!/usr/bin/env python3
"""
Behavioral Interview Prep for Staff+ Engineers
Simulates behavioral/leadership questions with STAR framework,
showing what Staff-level impact looks like vs Senior-level answers.
"""

import random
import time
import textwrap

# ============================================================================
# BEHAVIORAL QUESTIONS
# ============================================================================

QUESTIONS = [
    {
        "question": "Tell me about a time you changed the technical direction of your organization.",
        "star": {
            "situation": "Our org was building 5 separate ML pipelines with different frameworks, "
                        "causing maintenance burden and hindering cross-team collaboration.",
            "task": "I needed to align 5 teams (40+ engineers) on a unified ML platform "
                   "without top-down mandate and without blocking ongoing deliverables.",
            "action": [
                "Built a prototype showing 3x faster model deployment on unified platform",
                "Created an RFC and socialized it in 1:1s with each tech lead before the group review",
                "Identified early adopter team willing to pilot (lowest risk, highest visibility)",
                "Established migration path: teams adopt at natural transition points (not forced rewrite)",
                "Published weekly migration progress and wins to build momentum",
                "Paired with resistant teams to address their specific concerns",
            ],
            "result": "4/5 teams migrated within 6 months. Model deployment time reduced from "
                     "2 weeks to 2 days. Maintenance cost dropped 40%. The 5th team migrated "
                     "the following quarter after seeing results.",
        },
        "staff_signals": [
            "Org-wide impact (not just your team)",
            "Influence without authority (no mandate, built consensus)",
            "Strategic patience (migration path, not big-bang rewrite)",
            "Metrics-driven (3x faster, 40% cost reduction)",
            "Handled resistance constructively",
        ],
        "red_flags": [
            "'I convinced my manager to let me rewrite it' (too small scope)",
            "No mention of how others were brought along",
            "Result is individual contribution, not org-level change",
            "No metrics on impact",
        ],
    },
    {
        "question": "How did you handle a significant disagreement with another Staff engineer?",
        "star": {
            "situation": "Another Staff engineer advocated for building our own vector database. "
                        "I believed we should use a managed service. This was a $2M+/year decision "
                        "that would set architectural direction for 3+ years.",
            "task": "Reach the RIGHT decision (not 'win the argument'), maintain the relationship, "
                   "and give leadership enough information to decide.",
            "action": [
                "Acknowledged their expertise and valid points publicly",
                "Proposed a structured evaluation: define criteria together before comparing options",
                "Built a decision matrix with weighted factors (cost, ops burden, features, risk)",
                "Ran a time-boxed proof-of-concept for both approaches (2 weeks each)",
                "Presented findings jointly to leadership (not adversarially)",
                "When data supported managed service, offered to help them with their concerns about vendor lock-in",
            ],
            "result": "Went with managed service. Saved estimated $800K/year in engineering time. "
                     "Built in abstraction layer addressing lock-in concerns. Relationship with "
                     "the other engineer strengthened (they appreciated the rigorous process).",
        },
        "staff_signals": [
            "Focused on reaching the RIGHT answer, not winning",
            "Used data and structured evaluation (not politics)",
            "Maintained relationship and gave the other person respect",
            "Involved leadership appropriately (informed, not escalated)",
            "Showed the scale of the decision ($2M, 3 years)",
        ],
        "red_flags": [
            "'I proved them wrong' (adversarial framing)",
            "Escalated to management to get their way",
            "No data or evaluation framework",
            "The disagreement was about a trivial technical choice",
            "No mention of maintaining the relationship",
        ],
    },
    {
        "question": "Describe a time you made a wrong architectural decision. What did you learn?",
        "star": {
            "situation": "I chose to build a microservices architecture for our AI inference "
                        "platform when we had a team of 3. We spent 4 months on infrastructure "
                        "that a monolith could have handled in 1 month.",
            "task": "Recognize the mistake, course-correct without losing team trust or "
                   "momentum, and extract lasting lessons.",
            "action": [
                "Admitted the mistake openly in a team retro (didn't blame external factors)",
                "Analyzed WHY I made it: resume-driven development, didn't match team size to architecture",
                "Proposed consolidation plan: keep the clean interfaces but deploy as monolith",
                "Created a decision framework for future architecture choices (team size, scale projections)",
                "Shared the post-mortem org-wide as a learning opportunity",
            ],
            "result": "Consolidated in 3 weeks, shipped MVP 2 months 'late' but on solid foundation. "
                     "The decision framework became a standard part of our architecture review process. "
                     "Team trust actually increased because I owned the mistake and fixed it quickly.",
        },
        "staff_signals": [
            "Genuine ownership (not 'we made a mistake' or blaming context)",
            "Self-awareness about WHY (not just what went wrong)",
            "Quick course correction (didn't dig in due to sunk cost)",
            "Turned it into organizational learning (framework, shared post-mortem)",
            "Showed vulnerability built trust (counter-intuitive but true at Staff level)",
        ],
        "red_flags": [
            "'It wasn't really wrong, just ahead of its time'",
            "Blaming the team, timeline, or requirements",
            "The 'mistake' is actually a humble-brag",
            "No systemic learning (just 'I won't do that again')",
            "The mistake had no real consequences (low stakes)",
        ],
    },
    {
        "question": "Tell me about a time you had to make a decision with incomplete information.",
        "star": {
            "situation": "We needed to choose our LLM provider for a product launching in 6 weeks. "
                        "GPT-4 had reliability issues, Claude was new, and self-hosting was unproven "
                        "at our scale. No option was clearly superior.",
            "task": "Make a decision that unblocks 3 teams while managing risk and maintaining "
                   "flexibility to change if needed.",
            "action": [
                "Defined what 'good enough' meant for launch (latency, quality, cost thresholds)",
                "Built an abstraction layer making provider-switching a config change, not a rewrite",
                "Chose the option with lowest switching cost (API provider) for v1",
                "Set up evaluation framework to continuously compare options post-launch",
                "Defined trigger criteria: 'if X happens, we switch to Y' (pre-committed decision)",
                "Communicated the decision as 'v1 choice' not 'permanent architecture'",
            ],
            "result": "Launched on time. Switched providers once in first 3 months (took 2 days, "
                     "not 2 months, because of abstraction layer). The decision framework became "
                     "our standard approach for technology bets under uncertainty.",
        },
        "staff_signals": [
            "Recognized that not deciding was the worst option",
            "Designed for reversibility (reduce cost of being wrong)",
            "Pre-committed to decision criteria (avoided endless debate)",
            "Unblocked others (3 teams waiting)",
            "Framed as v1, not permanent (gave psychological safety to the choice)",
        ],
        "red_flags": [
            "Waited until they had 'perfect information' (delayed everyone)",
            "Made a permanent decision when a reversible one was possible",
            "Didn't consider the cost of being wrong",
            "Decision was actually low-stakes disguised as hard",
        ],
    },
    {
        "question": "How have you mentored or grown other engineers to higher levels?",
        "star": {
            "situation": "I had 3 senior engineers on my team who were 'stuck' - doing excellent "
                        "individual work but not demonstrating Staff-level behaviors (influence, "
                        "scope, technical vision).",
            "task": "Help them grow into Staff engineers without just telling them what to do "
                   "(which would be the anti-pattern of 'Staff by proxy').",
            "action": [
                "Had candid conversations about what Staff looks like (not just harder IC work)",
                "Created opportunities: assigned cross-team projects, sponsored RFC ownership",
                "Provided specific feedback on their design docs (not just 'LGTM' or 'needs work')",
                "Connected them with other Staff engineers for diverse perspectives",
                "Helped them find their own 'Staff story' (what unique impact only they could have)",
                "Advocated for their promotion when ready (with specific evidence)",
            ],
            "result": "2 of 3 promoted to Staff within 18 months. Third chose to go into management "
                     "instead (also a valid growth path). All three now mentor others similarly.",
        },
        "staff_signals": [
            "Multiplier effect (grew others, not just self)",
            "Specific, actionable growth strategies (not just 'I mentored')",
            "Created opportunities (not just gave advice)",
            "Recognized different growth paths (management track)",
            "The impact compounds (they now mentor others)",
        ],
        "red_flags": [
            "'I helped them with their code reviews' (too tactical)",
            "Generic mentoring (no specific strategies or outcomes)",
            "Only one person (narrow impact)",
            "No mention of THEIR growth, just task delegation",
        ],
    },
    {
        "question": "Describe how you identified and drove a technical initiative that wasn't on anyone's roadmap.",
        "star": {
            "situation": "I noticed our AI model evaluation was ad-hoc: every team had their own "
                        "scripts, results weren't comparable, and nobody knew if models were "
                        "degrading in production. This was creating silent quality issues.",
            "task": "Get organizational buy-in for an evaluation platform when no team owned it "
                   "and nobody was asking for it (yet).",
            "action": [
                "Documented 3 production incidents caused by undetected model degradation",
                "Calculated the cost: 2 engineering-weeks per team per quarter on ad-hoc eval",
                "Built a minimal prototype (1 week of my time) showing unified dashboard",
                "Presented to engineering leadership with the business case (risk + cost + prototype)",
                "Got 20% time allocation from 2 teams, grew to dedicated team in Q2",
                "Defined success metrics: time-to-detect degradation, eval setup time per model",
            ],
            "result": "Platform adopted by 8 teams. Detected 3 model degradations that would have "
                     "hit production. Eval setup time went from 2 weeks to 2 hours. Got funded as "
                     "a full team in the following planning cycle.",
        },
        "staff_signals": [
            "Identified a problem nobody was articulating yet",
            "Built the business case (not just 'this is cool technically')",
            "Started with minimal investment to prove value",
            "Grew organically through demonstrated impact",
            "Thought about it as a PRODUCT with users and success metrics",
        ],
        "red_flags": [
            "The initiative was actually assigned to them",
            "No business justification (just technical interest)",
            "Built it in isolation without adoption",
            "No metrics on impact",
        ],
    },
]

# ============================================================================
# DISPLAY
# ============================================================================

def print_header(text, char="="):
    width = 78
    print(f"\n{char * width}")
    print(f" {text}")
    print(f"{char * width}")


def run_behavioral_prep():
    print_header("BEHAVIORAL INTERVIEW PREP FOR STAFF+ ENGINEERS")
    print("""
    Staff+ behavioral interviews test for:
    - Org-level impact (not just team-level)
    - Influence without authority
    - Technical vision and strategy
    - Growing others (multiplier effect)
    - Handling ambiguity and conflict constructively

    Format: STAR (Situation, Task, Action, Result)
    """)

    # Present 3 random questions
    selected = random.sample(QUESTIONS, min(3, len(QUESTIONS)))

    for i, q in enumerate(selected, 1):
        print_header(f"QUESTION {i}/3", "-")
        print(f"\n  \"{q['question']}\"\n")
        time.sleep(0.5)

        print("  ┌─────────────────────────────────────────────────────────────────┐")
        print("  │ Think about YOUR answer using STAR before reading the example.  │")
        print("  └─────────────────────────────────────────────────────────────────┘")
        time.sleep(0.5)

        # STAR example
        star = q["star"]
        print(f"\n  EXAMPLE STAFF-LEVEL ANSWER (STAR):")
        print(f"\n  SITUATION:")
        for line in textwrap.wrap(star["situation"], 70):
            print(f"    {line}")
        print(f"\n  TASK:")
        for line in textwrap.wrap(star["task"], 70):
            print(f"    {line}")
        print(f"\n  ACTION:")
        for action in star["action"]:
            print(f"    - {action}")
        print(f"\n  RESULT:")
        for line in textwrap.wrap(star["result"], 70):
            print(f"    {line}")

        # Signals
        print(f"\n  GREEN FLAGS (Staff-level signals):")
        for s in q["staff_signals"]:
            print(f"    + {s}")

        print(f"\n  RED FLAGS (sounds Senior, not Staff):")
        for r in q["red_flags"]:
            print(f"    - {r}")

        print()

    # General guidance
    print_header("GENERAL GUIDANCE FOR STAFF+ BEHAVIORAL INTERVIEWS")
    print("""
  THE STAFF DIFFERENCE:

  Senior answers sound like:     Staff answers sound like:
  ─────────────────────────      ─────────────────────────────────────
  "I built X"                    "I identified the need for X and got 3 teams to adopt it"
  "I fixed the bug"              "I fixed the system so this class of bug can't happen"
  "I disagreed and was right"    "I created a framework for making this type of decision"
  "I mentored someone"           "I created an environment where 5 people grew to Staff"
  "I delivered on time"          "I redefined what we should be delivering"

  PREPARATION CHECKLIST:
    [ ] Have 5-7 stories ready covering: conflict, failure, influence, growth, vision
    [ ] Each story has QUANTIFIED impact (dollars, people, time, percentage)
    [ ] Each story shows ORG-LEVEL scope (not just your team)
    [ ] Each story shows LASTING change (not one-time fix)
    [ ] Practice telling each story in 3-4 minutes (not 10)
    [ ] Have follow-up details ready (interviewers will probe)

  COMMON MISTAKES:
    1. Stories too small in scope (team-level, not org-level)
    2. No metrics (how do we know it mattered?)
    3. Hero narrative (you did everything alone)
    4. No learning/growth arc (you were already perfect)
    5. Too long (5+ minutes without structure)
    """)

    print(f"  Run again for different questions ({len(QUESTIONS)} in bank).\n")


if __name__ == "__main__":
    run_behavioral_prep()
