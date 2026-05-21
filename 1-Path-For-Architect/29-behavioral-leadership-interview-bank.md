# Behavioral and Architecture Leadership Interview Bank

Architect interviews are not only about technical design. At staff, principal, and architect levels, interviewers test judgment, influence, ownership, and communication.

## Leadership Answer Formula

Use this structure:

```text
Context -> Stakes -> Constraints -> Options -> Decision -> Execution -> Result -> Reflection
```

Do not give only a story. Explain the trade-off and what you learned.

## Core Leadership Themes

| Theme | What Interviewers Test |
| --- | --- |
| Influence without authority | Can you align teams without direct control? |
| Technical judgment | Can you choose boring, reliable solutions when needed? |
| Conflict handling | Can you disagree constructively and use evidence? |
| Ownership | Do you care about production after launch? |
| Migration leadership | Can you reduce risk while changing critical systems? |
| Incident leadership | Can you stay structured under pressure? |
| Mentorship | Can you raise team quality? |
| Business alignment | Can you connect architecture to outcomes? |
| Cost awareness | Can you balance reliability, speed, and spend? |
| Security mindset | Can you protect users and the company? |

## Story Bank Template

Prepare at least 12 stories.

```markdown
# Story: Title

## Context
...

## Stakes
...

## Constraints
...

## Options Considered
...

## Decision
...

## Execution
...

## Result
...

## What I Would Do Differently
...
```

## Must-Have Stories

1. Led a complex technical migration.
2. Resolved disagreement between teams.
3. Improved reliability after an incident.
4. Made a trade-off between speed and correctness.
5. Reduced operational cost.
6. Simplified an over-engineered architecture.
7. Introduced a standard or platform capability.
8. Managed a production incident.
9. Pushed back on a risky requirement.
10. Changed your mind after new evidence.
11. Mentored engineers through a design.
12. Balanced security/compliance with delivery pressure.

## Question Bank

### Influence

- Tell me about a time you influenced a team without authority.
- How do you drive adoption of a platform standard?
- How do you handle a team that refuses an architecture recommendation?
- How do you get buy-in for migration work that product does not directly see?

### Technical Judgment

- Tell me about a time you chose a simpler architecture over a more advanced one.
- Tell me about a time a technology choice did not work out.
- How do you decide when to build vs buy?
- How do you decide when microservices are justified?

### Conflict

- Tell me about a time you disagreed with another senior engineer.
- Tell me about a time you disagreed with product or leadership.
- How do you handle architecture review conflict?
- How do you handle a team optimizing locally but hurting the platform?

### Incidents and Reliability

- Tell me about the worst production incident you handled.
- What did you change after an incident?
- How do you decide whether to roll back or hotfix?
- How do you prevent repeated incidents?

### Migration

- Tell me about a migration you led.
- How did you reduce migration risk?
- How did you measure progress?
- How did you handle rollback?

### Cost

- Tell me about a time you reduced infrastructure cost.
- How do you discuss cost without harming reliability?
- How do you allocate shared platform cost?
- How do you prevent teams from over-provisioning?

### Security and Compliance

- Tell me about a time you improved security posture.
- How do you handle a risky launch with compliance concerns?
- How do you design auditability into systems?
- How do you balance developer productivity and security guardrails?

## Weak vs Strong Answers

### Weak

- "I told the team what to do."
- "We used Kafka because it scales."
- "The incident happened because someone deployed bad code."
- "I reduced cost by using smaller instances."

### Strong

- "I framed the decision around the reliability target and migration risk."
- "I compared Kafka, SQS, and direct calls against ordering, replay, operational burden, and team maturity."
- "The incident exposed a missing canary gate and an alert that watched infrastructure instead of user symptoms."
- "We reduced cost by measuring unit economics, rightsizing, lowering retention, and changing the workload pattern."

## Seniority Signals

Staff/principal/architect answers show:

- System-level thinking.
- Calm trade-off framing.
- Evidence-based disagreement.
- Clear ownership.
- Bias toward measurable outcomes.
- Respect for operational burden.
- Strong rollback and migration thinking.
- User and business awareness.
- Ability to teach without condescension.

## Practice Drill

For each story:

1. Write the short version in 2 minutes.
2. Write the deep version in 6 minutes.
3. Add the trade-off.
4. Add the measurable result.
5. Add the lesson learned.
6. Practice answering follow-up questions.

Follow-up questions to expect:

- What alternatives did you consider?
- What was your role specifically?
- What data changed your mind?
- What would you do differently?
- How did you measure success?
- How did you communicate risk?
- How did you handle disagreement?
- What was the long-term impact?

