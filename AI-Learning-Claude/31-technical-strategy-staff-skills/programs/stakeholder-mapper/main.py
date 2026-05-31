"""
Stakeholder Mapper and Communication Planner
=============================================
Maps stakeholders by influence and interest, generates tailored
communication plans, and demonstrates the pre-socialization workflow
that Staff Architects use to drive organizational change.

Usage: python3 main.py

No external dependencies required.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple
from enum import Enum


class Influence(Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class Interest(Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class Position(Enum):
    CHAMPION = "CHAMPION"      # Actively supports
    SUPPORTER = "SUPPORTER"    # Generally positive
    NEUTRAL = "NEUTRAL"        # No strong opinion
    SKEPTIC = "SKEPTIC"        # Has concerns
    BLOCKER = "BLOCKER"        # Actively opposes


@dataclass
class Stakeholder:
    name: str
    role: str
    influence: Influence
    interest: Interest
    position: Position
    core_concern: str
    what_they_value: str
    communication_preference: str  # document, 1:1, presentation, prototype


@dataclass 
class CommunicationPlan:
    stakeholder: Stakeholder
    strategy: str
    message_framing: str
    timing: str
    medium: str
    success_criteria: str


def create_stakeholders() -> List[Stakeholder]:
    """
    Create a realistic set of stakeholders for an AI platform initiative.
    
    TEACHING POINT: Stakeholder mapping isn't optional for Staff architects.
    If you skip this step, you'll be surprised by resistance that was
    entirely predictable. Map BEFORE you write your proposal.
    """
    return [
        Stakeholder(
            name="Sarah (VP of Engineering)",
            role="Engineering VP - owns budget and headcount",
            influence=Influence.HIGH,
            interest=Interest.HIGH,
            position=Position.SUPPORTER,
            core_concern="ROI timeline - needs to justify investment to CFO",
            what_they_value="Clear metrics, cost reduction, competitive advantage",
            communication_preference="1:1 with executive summary",
        ),
        Stakeholder(
            name="Marcus (Platform Team EM)",
            role="Engineering Manager - platform team (your partner)",
            influence=Influence.HIGH,
            interest=Interest.HIGH,
            position=Position.CHAMPION,
            core_concern="Team capacity - his team will build this",
            what_they_value="Clear scope, phased delivery, team growth opportunity",
            communication_preference="Co-author the document together",
        ),
        Stakeholder(
            name="Priya (Product Eng Lead - Search)",
            role="Tech Lead - largest AI consumer team",
            influence=Influence.MEDIUM,
            interest=Interest.HIGH,
            position=Position.SKEPTIC,
            core_concern="Migration burden - her team has deadlines",
            what_they_value="Zero downtime migration, no feature regression, autonomy",
            communication_preference="Technical deep-dive with her team",
        ),
        Stakeholder(
            name="James (SRE Lead)",
            role="SRE Lead - owns reliability",
            influence=Influence.MEDIUM,
            interest=Interest.HIGH,
            position=Position.NEUTRAL,
            core_concern="Operational complexity - another system to page on",
            what_they_value="Observability, runbooks, reduced incident surface area",
            communication_preference="Detailed technical design review",
        ),
        Stakeholder(
            name="Lisa (Product VP)",
            role="VP of Product - owns roadmap",
            influence=Influence.HIGH,
            interest=Interest.MEDIUM,
            position=Position.NEUTRAL,
            core_concern="Feature velocity - will this slow us down?",
            what_they_value="Faster time-to-market, customer satisfaction",
            communication_preference="Brief 1:1, business-focused framing",
        ),
        Stakeholder(
            name="David (Finance Partner)",
            role="Finance Business Partner - controls budget approval",
            influence=Influence.MEDIUM,
            interest=Interest.LOW,
            position=Position.NEUTRAL,
            core_concern="Cost trajectory - needs predictable spend",
            what_they_value="Clear ROI model, cost projections, break-even timeline",
            communication_preference="Spreadsheet with numbers",
        ),
        Stakeholder(
            name="Raj (ML Infra Senior Eng)",
            role="Senior Engineer - most experienced ML infra person",
            influence=Influence.LOW,
            interest=Interest.HIGH,
            position=Position.BLOCKER,
            core_concern="'We tried this before and it failed' - burned by past platform",
            what_they_value="Technical excellence, proven approaches, not repeating mistakes",
            communication_preference="1:1 deep technical discussion, show prototype",
        ),
        Stakeholder(
            name="Amy (Product Eng Lead - Support Bot)",
            role="Tech Lead - second largest AI consumer",
            influence=Influence.LOW,
            interest=Interest.MEDIUM,
            position=Position.SUPPORTER,
            core_concern="Will the platform actually serve her use case?",
            what_they_value="Good documentation, responsive platform team, flexibility",
            communication_preference="Workshop/demo",
        ),
    ]


def generate_influence_interest_grid(stakeholders: List[Stakeholder]) -> None:
    """
    Display the classic influence/interest matrix.
    
    TEACHING POINT: This quadrant determines your engagement strategy:
    - High influence + High interest: Manage closely (your key players)
    - High influence + Low interest: Keep satisfied (don't surprise them)
    - Low influence + High interest: Keep informed (they're your advocates)
    - Low influence + Low interest: Monitor (don't over-invest)
    """
    print()
    print("  INFLUENCE / INTEREST MATRIX")
    print()
    print("              HIGH INTEREST                    LOW INTEREST")
    print("  ┌────────────────────────────────┬──────────────────────────────┐")
    print("  │                                │                              │")
    print("  │   MANAGE CLOSELY               │   KEEP SATISFIED             │")
    print("  │   (Key Players)                │   (Don't surprise them)      │")
    
    hi_hi = [s for s in stakeholders if s.influence == Influence.HIGH and s.interest == Interest.HIGH]
    hi_lo = [s for s in stakeholders if s.influence == Influence.HIGH and s.interest in (Interest.LOW, Interest.MEDIUM)]
    
    max_rows = max(len(hi_hi), len(hi_lo), 1)
    for i in range(max_rows):
        left = f"   • {hi_hi[i].name}" if i < len(hi_hi) else ""
        right = f"   • {hi_lo[i].name}" if i < len(hi_lo) else ""
        print(f"H │{left:<33}│{right:<31}│")
    
    print("I │                                │                              │")
    print("N ├────────────────────────────────┼──────────────────────────────┤")
    print("F │                                │                              │")
    print("L │   KEEP INFORMED                │   MONITOR                    │")
    print("U │   (Your advocates)             │   (Minimal effort)           │")
    
    lo_hi = [s for s in stakeholders if s.influence in (Influence.LOW, Influence.MEDIUM) and s.interest == Interest.HIGH]
    lo_lo = [s for s in stakeholders if s.influence == Influence.LOW and s.interest == Interest.LOW]
    
    max_rows = max(len(lo_hi), len(lo_lo), 1)
    for i in range(max_rows):
        left = f"   • {lo_hi[i].name}" if i < len(lo_hi) else ""
        right = f"   • {lo_lo[i].name}" if i < len(lo_lo) else ""
        print(f"  │{left:<33}│{right:<31}│")
    
    print("  │                                │                              │")
    print("  └────────────────────────────────┴──────────────────────────────┘")


def generate_communication_plans(stakeholders: List[Stakeholder]) -> List[CommunicationPlan]:
    """
    Generate tailored communication plans for each stakeholder.
    
    TEACHING POINT: The same proposal needs different framing for different
    audiences. This isn't manipulation - it's communication competence.
    An engineer cares about technical elegance. A VP cares about business impact.
    Same truth, different lens.
    """
    plans = []
    
    for s in stakeholders:
        if s.position == Position.CHAMPION:
            strategy = "Empower as co-advocate. Give them the narrative to spread."
            timing = "Early - involve in drafting"
        elif s.position == Position.SUPPORTER:
            strategy = "Reinforce support. Share progress. Ask for public endorsement."
            timing = "Early - share draft for input"
        elif s.position == Position.NEUTRAL:
            strategy = "Educate and address concerns proactively. Make it easy to say yes."
            timing = "Before formal review - 1:1 conversation"
        elif s.position == Position.SKEPTIC:
            strategy = "Listen deeply. Address concerns in the document. Offer pilot/trial."
            timing = "Early and often - multiple touchpoints"
        else:  # BLOCKER
            strategy = "Understand root cause of opposition. Find common ground. Prototype to prove."
            timing = "Earliest - before anyone else sees the proposal"
        
        # Tailor message based on what they value
        if "cost" in s.what_they_value.lower() or "roi" in s.what_they_value.lower():
            framing = "Lead with cost savings and ROI timeline. Show the math."
        elif "velocity" in s.what_they_value.lower() or "faster" in s.what_they_value.lower():
            framing = "Lead with speed improvement. 'New features in days not weeks.'"
        elif "reliability" in s.what_they_value.lower() or "observability" in s.what_they_value.lower():
            framing = "Lead with operational improvement. Show how this REDUCES their burden."
        elif "autonomy" in s.what_they_value.lower() or "flexibility" in s.what_they_value.lower():
            framing = "Lead with what they KEEP control of. Emphasize the escape hatch."
        elif "technical" in s.what_they_value.lower() or "proven" in s.what_they_value.lower():
            framing = "Lead with technical depth. Show the prototype. Acknowledge past failures."
        else:
            framing = "Lead with their specific pain point being solved."
        
        # Success criteria
        if s.position in (Position.BLOCKER, Position.SKEPTIC):
            success = "Moves to Neutral or Supporter. Concerns addressed in document."
        elif s.position == Position.NEUTRAL:
            success = "Actively supports or at minimum won't block."
        else:
            success = "Publicly advocates. Helps convince others."
        
        plans.append(CommunicationPlan(
            stakeholder=s,
            strategy=strategy,
            message_framing=framing,
            timing=timing,
            medium=s.communication_preference,
            success_criteria=success,
        ))
    
    return plans


def generate_pre_socialization_checklist(plans: List[CommunicationPlan]) -> None:
    """Generate a pre-socialization checklist ordered by priority."""
    print()
    print("=" * 70)
    print("  PRE-SOCIALIZATION CHECKLIST")
    print("  (Complete BEFORE formal review)")
    print("=" * 70)
    print()
    
    # Sort: blockers first, then skeptics, then neutrals, then supporters
    priority_order = {
        Position.BLOCKER: 0,
        Position.SKEPTIC: 1,
        Position.NEUTRAL: 2,
        Position.SUPPORTER: 3,
        Position.CHAMPION: 4,
    }
    
    sorted_plans = sorted(plans, key=lambda p: priority_order[p.stakeholder.position])
    
    print("  💡 TEACHING POINT: Talk to BLOCKERS and SKEPTICS first.")
    print("     If you talk to supporters first, you build false confidence.")
    print("     If you talk to blockers first, you can address their concerns")
    print("     in the document before anyone else sees it.")
    print()
    
    for i, plan in enumerate(sorted_plans, 1):
        s = plan.stakeholder
        pos_marker = {
            Position.BLOCKER: "🔴",
            Position.SKEPTIC: "🟡",
            Position.NEUTRAL: "⚪",
            Position.SUPPORTER: "🟢",
            Position.CHAMPION: "💚",
        }[s.position]
        
        print(f"  {pos_marker} Step {i}: {s.name} ({s.position.value})")
        print(f"     Role: {s.role}")
        print(f"     Concern: {s.core_concern}")
        print(f"     Strategy: {plan.strategy}")
        print(f"     Framing: {plan.message_framing}")
        print(f"     Medium: {plan.medium}")
        print(f"     Timing: {plan.timing}")
        print(f"     Success: {plan.success_criteria}")
        print(f"     [ ] Scheduled  [ ] Completed  [ ] Concerns documented")
        print()


def demonstrate_audience_tailoring() -> None:
    """
    Show how the same message is tailored for different audiences.
    
    TEACHING POINT: This is a critical Staff skill. The same technical
    truth needs different framing for different audiences. This isn't
    being political - it's being an effective communicator.
    """
    print()
    print("=" * 70)
    print("  MESSAGE TAILORING: Same Proposal, Different Audiences")
    print("=" * 70)
    print()
    
    proposal = "Build a unified model gateway for the AI platform"
    
    audiences = {
        "Engineers (Technical Depth)": (
            "We're building an intent-based model gateway. You'll declare "
            "(quality='high', max_latency_ms=3000, max_cost_cents=5) and the "
            "gateway handles provider selection, failover, and caching. Your "
            "code gets simpler - no more provider-specific error handling or "
            "manual retry logic. Here's the API..."
        ),
        "Engineering Director (Team Impact)": (
            "This reduces your team's AI infrastructure burden by 60%. Instead "
            "of each team maintaining model integrations and failover logic, "
            "they call one API. Onboarding new AI features goes from 3 weeks to "
            "2 days. Your engineers focus on product logic, not infrastructure. "
            "Migration is phased - no big bang."
        ),
        "VP of Product (Business Outcomes)": (
            "New AI features ship in days instead of weeks. Provider outages "
            "become invisible to customers (automatic failover). We can adopt "
            "new models like GPT-5 in days, not months - staying ahead of "
            "competitors. No impact on current feature velocity during migration."
        ),
        "CFO / Finance (ROI)": (
            "Investment: $500K (3 engineers, 6 months). Return: $3.6M annually "
            "in cost savings from intelligent routing and caching. Break-even: "
            "Month 4. Additionally eliminates ~$800K/year in outage revenue loss. "
            "Payback period: 3 months post-completion."
        ),
        "Skeptical Senior Engineer (Past Failures)": (
            "I know the last platform attempt failed. Here's what's different: "
            "(1) We're starting with 2 volunteer teams, not mandating migration. "
            "(2) We have a working prototype - I'll demo it. (3) There's an "
            "escape hatch - teams can bypass the gateway if needed. What concerns "
            "do you have that I should address in the design?"
        ),
    }
    
    for audience, message in audiences.items():
        print(f"  TO: {audience}")
        print(f"  ─{'─' * 60}")
        # Wrap text nicely
        words = message.split()
        line = "  "
        for word in words:
            if len(line) + len(word) + 1 > 68:
                print(line)
                line = "  " + word
            else:
                line += " " + word if line.strip() else "  " + word
        if line.strip():
            print(line)
        print()
    
    print("  💡 KEY INSIGHT: Same underlying truth. Different emphasis.")
    print("     Engineers need HOW. Directors need IMPACT. VPs need OUTCOMES.")
    print("     Finance needs NUMBERS. Skeptics need ACKNOWLEDGMENT + PROOF.")


def writing_is_thinking_workflow() -> None:
    """Demonstrate the 'writing is thinking' workflow."""
    print()
    print("=" * 70)
    print("  THE 'WRITING IS THINKING' WORKFLOW")
    print("=" * 70)
    print()
    print("  Most people think: Write document → Get feedback → Revise")
    print("  Staff architects know: Writing IS the thinking process.")
    print()
    
    workflow = [
        ("1. THINK by writing (alone)", [
            "Write the ugliest first draft. Get ideas OUT of your head.",
            "Don't edit. Don't polish. Just capture reasoning.",
            "Goal: Expose your own assumptions to yourself.",
        ]),
        ("2. STRESS-TEST by sharing (1-2 trusted peers)", [
            "Share the rough draft with 1-2 people you trust.",
            "'Here's my thinking. Where am I wrong?'",
            "Goal: Find blind spots before investing in polish.",
        ]),
        ("3. REFINE based on feedback (alone again)", [
            "Incorporate feedback. Now the structure should emerge.",
            "Write the 'Alternatives Considered' - this sharpens your reasoning.",
            "Goal: Document that can withstand scrutiny.",
        ]),
        ("4. PRE-SOCIALIZE (key stakeholders, 1:1)", [
            "Walk stakeholders through the doc in 1:1s.",
            "Listen more than you talk. Note concerns.",
            "Goal: No surprises in the formal review.",
        ]),
        ("5. PUBLISH for review (broader audience)", [
            "By now, the document is battle-tested.",
            "Formal review should be ratification, not revelation.",
            "Goal: Alignment and decision.",
        ]),
    ]
    
    for step_name, details in workflow:
        print(f"  {step_name}")
        for d in details:
            print(f"    • {d}")
        print()
    
    print("  TIME INVESTMENT:")
    print("    Step 1: 2-4 hours (one focused session)")
    print("    Step 2: 1-2 days (waiting for feedback)")
    print("    Step 3: 2-3 hours")
    print("    Step 4: 1-2 weeks (scheduling stakeholder 1:1s)")
    print("    Step 5: 1 week (formal review period)")
    print()
    print("    Total: ~3-4 weeks for a major strategy document")
    print("    This feels slow but it's MUCH faster than:")
    print("    'Write perfect doc → Present → Get destroyed → Start over'")


def main():
    """Main execution flow."""
    print("=" * 70)
    print("  STAKEHOLDER MAPPER & COMMUNICATION PLANNER")
    print("=" * 70)
    print()
    print("  This tool demonstrates how Staff Architects plan organizational")
    print("  change. The insight: technical excellence is necessary but not")
    print("  sufficient. You must understand and navigate people.")
    print()
    print("  💡 TEACHING POINT: If you skip stakeholder mapping, you will:")
    print("     - Be surprised by resistance you could have predicted")
    print("     - Fail to frame your proposal for your audience")
    print("     - Waste months on a proposal that gets blocked")
    print()
    
    # Step 1: Map stakeholders
    print("─" * 70)
    print("  STEP 1: IDENTIFY STAKEHOLDERS")
    print("─" * 70)
    
    stakeholders = create_stakeholders()
    
    print()
    print(f"  Identified {len(stakeholders)} stakeholders:")
    print()
    for s in stakeholders:
        pos_color = {
            Position.CHAMPION: "💚",
            Position.SUPPORTER: "🟢",
            Position.NEUTRAL: "⚪",
            Position.SKEPTIC: "🟡",
            Position.BLOCKER: "🔴",
        }[s.position]
        print(f"  {pos_color} {s.name} [{s.influence.value} influence, {s.interest.value} interest]")
        print(f"     Concern: {s.core_concern}")
        print()
    
    # Step 2: Influence/Interest Grid
    print("─" * 70)
    print("  STEP 2: INFLUENCE / INTEREST MATRIX")
    print("─" * 70)
    generate_influence_interest_grid(stakeholders)
    
    # Step 3: Communication Plans
    print()
    print("─" * 70)
    print("  STEP 3: COMMUNICATION PLANS")
    print("─" * 70)
    plans = generate_communication_plans(stakeholders)
    
    # Step 4: Pre-socialization checklist
    generate_pre_socialization_checklist(plans)
    
    # Step 5: Message tailoring demo
    demonstrate_audience_tailoring()
    
    # Step 6: Writing workflow
    writing_is_thinking_workflow()
    
    # Summary
    print()
    print("=" * 70)
    print("  KEY LESSONS")
    print("=" * 70)
    print("""
  1. MAP BEFORE YOU WRITE: Know your audience before crafting the message.
  
  2. BLOCKERS FIRST: Talk to opponents early. Their concerns improve your doc.
  
  3. SAME TRUTH, DIFFERENT LENS: Tailor framing, not facts.
  
  4. WRITING IS THINKING: The document is how you develop the idea,
     not just how you communicate it.
  
  5. PRE-SOCIALIZE EVERYTHING: If the review meeting has surprises,
     you failed at stakeholder management.
  
  6. PATIENCE: Organizational change takes 2-3x longer than you expect.
     Plan for it. Don't get frustrated.
  
  The Staff Architect's uncomfortable truth: being right about
  architecture is the EASY part. Getting an organization to adopt
  it is the hard part. This tool helps with the hard part.
""")


if __name__ == "__main__":
    main()
