# Multi-Agent Systems: Real-World Examples

## Case Study 1: Due Diligence Research with Supervisor-Worker Architecture

### Context

Meridian Consulting, a strategy firm, built a multi-agent system to automate the first 80% of M&A due diligence. Previously, a team of 6 analysts spent 3 weeks per deal. The AI system produces a draft report in 4 hours.

### Architecture

```
                    ┌─────────────────────┐
                    │   Supervisor Agent   │
                    │  (GPT-4o, orchestr.) │
                    └──────────┬──────────┘
                               │
            ┌──────────────────┼──────────────────┐
            │                  │                  │
   ┌────────▼────────┐ ┌──────▼──────┐ ┌────────▼────────┐
   │  Legal Analyst   │ │  Financial  │ │ Market Research  │
   │  Agent           │ │  Analyst    │ │ Agent            │
   │  (Claude, tools) │ │  (GPT-4o)  │ │ (GPT-4o-mini)   │
   └────────┬────────┘ └──────┬──────┘ └────────┬────────┘
            │                  │                  │
   ┌────────▼────────┐ ┌──────▼──────┐ ┌────────▼────────┐
   │  SEC Filings    │ │  Bloomberg  │ │  News APIs      │
   │  Patent DBs     │ │  S&P Data   │ │  Industry DBs   │
   │  Court Records  │ │  Tax Docs   │ │  Competitor Intel│
   └─────────────────┘ └─────────────┘ └─────────────────┘
```

### Supervisor Agent Implementation

```python
class DueDiligenceSupervisor:
    """
    Coordinates 3 specialist agents for M&A due diligence.
    Responsible for: task decomposition, dependency management,
    quality gates, conflict resolution, and report synthesis.
    """

    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0)
        self.agents = {
            "legal": LegalAnalystAgent(),
            "financial": FinancialAnalystAgent(),
            "market": MarketResearchAgent(),
        }
        self.state = DueDiligenceState()
        self.quality_checker = QualityGateAgent()

    async def run_due_diligence(self, target_company: str, deal_context: dict) -> Report:
        # Phase 1: Supervisor decomposes the task
        plan = await self._create_plan(target_company, deal_context)
        # Example plan output:
        # {
        #   "legal_tasks": [
        #     "Review corporate structure and subsidiaries",
        #     "Identify pending litigation > $1M",
        #     "Check IP portfolio and patent expiry dates",
        #     "Review material contracts and change-of-control clauses"
        #   ],
        #   "financial_tasks": [
        #     "Analyze 3-year revenue trends and margins",
        #     "Identify off-balance-sheet liabilities",
        #     "Model customer concentration risk",
        #     "Assess working capital requirements"
        #   ],
        #   "market_tasks": [
        #     "Map competitive landscape and market share",
        #     "Identify regulatory risks in key markets",
        #     "Assess TAM/SAM/SOM with growth projections",
        #     "Evaluate technology moat durability"
        #   ],
        #   "dependencies": [
        #     {"from": "financial.revenue_analysis", "to": "market.market_share"},
        #     {"from": "legal.ip_portfolio", "to": "market.technology_moat"}
        #   ]
        # }

        # Phase 2: Execute independent tasks in parallel
        independent_results = await asyncio.gather(
            self.agents["legal"].execute(plan["legal_tasks"][:2]),
            self.agents["financial"].execute(plan["financial_tasks"][:2]),
            self.agents["market"].execute(plan["market_tasks"][:2]),
        )

        # Phase 3: Update shared state, execute dependent tasks
        self.state.update(independent_results)

        dependent_results = await asyncio.gather(
            self.agents["financial"].execute(
                plan["financial_tasks"][2:],
                context=self.state.get("legal.corporate_structure")
            ),
            self.agents["market"].execute(
                plan["market_tasks"][2:],
                context=self.state.get("financial.revenue_data")
            ),
        )
        self.state.update(dependent_results)

        # Phase 4: Quality gate — supervisor reviews for gaps
        gaps = await self._identify_gaps(self.state)
        if gaps:
            fill_results = await self._fill_gaps(gaps)
            self.state.update(fill_results)

        # Phase 5: Conflict resolution
        conflicts = await self._detect_conflicts(self.state)
        # Example conflict: Legal says "no material litigation"
        # but Financial found a $50M contingent liability reference
        for conflict in conflicts:
            resolution = await self._resolve_conflict(conflict)
            self.state.update_resolution(conflict.id, resolution)

        # Phase 6: Synthesize final report
        report = await self._synthesize_report(self.state)
        return report

    async def _resolve_conflict(self, conflict: Conflict) -> Resolution:
        """
        Supervisor mediates between agents when findings contradict.
        Strategy: Ask both agents to provide evidence, then judge.
        """
        evidence_a = await self.agents[conflict.agent_a].provide_evidence(
            conflict.claim_a, max_sources=5
        )
        evidence_b = await self.agents[conflict.agent_b].provide_evidence(
            conflict.claim_b, max_sources=5
        )

        resolution_prompt = f"""
        Two analysts disagree on: {conflict.topic}

        Analyst A ({conflict.agent_a}) claims: {conflict.claim_a}
        Evidence: {evidence_a}

        Analyst B ({conflict.agent_b}) claims: {conflict.claim_b}
        Evidence: {evidence_b}

        Determine which is more supported by evidence. If uncertain,
        flag for human review with explanation of ambiguity.
        """

        result = await self.llm.ainvoke(resolution_prompt)
        return Resolution(
            topic=conflict.topic,
            conclusion=result.content,
            confidence=self._extract_confidence(result),
            needs_human_review=self._extract_confidence(result) < 0.7
        )
```

### Cost and Performance Metrics

```
Per due diligence run (typical Fortune 500 target):
├── Supervisor agent: ~15K tokens input, ~5K output × 8 calls = $0.80
├── Legal analyst: ~100K tokens input, ~20K output × 12 calls = $4.20
├── Financial analyst: ~80K tokens input, ~15K output × 10 calls = $3.10
├── Market research: ~60K tokens input, ~12K output × 8 calls = $1.80
├── Quality gate: ~30K tokens input, ~5K output × 3 calls = $0.60
└── Report synthesis: ~50K tokens input, ~10K output × 1 call = $0.50
                                                          Total: ~$11.00

Time: 3.5-4.5 hours (parallelized)
Previous cost: 6 analysts × 3 weeks × $150/hr = $108,000
ROI: 9,800x cost reduction (with human review adding ~$2,000 for 4 hours of senior review)
```

---

## Case Study 2: Debate-and-Judge for Code Review

### Context

CodeForge, an AI coding platform, uses a debate pattern for high-stakes code changes (security-sensitive, performance-critical, or architectural decisions). Two adversarial agents argue for/against the code, and a judge agent makes the final call.

### Architecture

```python
class DebateCodeReview:
    """
    Two agents debate code quality. One advocates for approval,
    one argues for rejection. Judge synthesizes a decision.

    Why debate works better than single-agent review:
    - Single agent tends to approve (bias toward "looks fine")
    - Debate surfaces edge cases neither would find alone
    - Judge sees both perspectives, makes more calibrated decisions
    - Measured: 34% more bugs caught vs single-agent review
    """

    def __init__(self):
        self.advocate = Agent(
            role="code_advocate",
            model="claude-sonnet-4-20250514",
            system_prompt="""You are a senior engineer advocating FOR this code change.
            Find the strongest arguments for why this code should be merged:
            - Identify design strengths
            - Note good patterns and practices
            - Argue why concerns raised are acceptable tradeoffs
            - Point out tests that validate correctness
            Be intellectually honest but find the best case for approval."""
        )

        self.critic = Agent(
            role="code_critic",
            model="claude-sonnet-4-20250514",
            system_prompt="""You are a senior engineer arguing AGAINST this code change.
            Find the strongest arguments for why this code needs revision:
            - Identify potential bugs, race conditions, edge cases
            - Note security vulnerabilities or performance risks
            - Find missing error handling or test coverage gaps
            - Identify architectural concerns or tech debt
            Be fair but thorough in finding legitimate issues."""
        )

        self.judge = Agent(
            role="code_judge",
            model="gpt-4o",
            system_prompt="""You are a principal engineer making the final review decision.
            You will see arguments from an advocate and a critic.
            Your job:
            1. Evaluate which arguments are substantive vs nitpicks
            2. Determine if issues are blocking or advisory
            3. Decide: APPROVE, REQUEST_CHANGES, or NEEDS_DISCUSSION
            4. Provide specific, actionable feedback
            Be calibrated: not every issue is blocking."""
        )

    async def review(self, pull_request: PullRequest) -> ReviewDecision:
        diff = pull_request.get_diff()
        context = pull_request.get_file_context(surrounding_lines=50)

        # Round 1: Initial arguments
        advocate_r1 = await self.advocate.argue(
            diff=diff, context=context,
            instruction="Present your case for approval."
        )
        critic_r1 = await self.critic.argue(
            diff=diff, context=context,
            instruction="Present your case for revision."
        )

        # Round 2: Rebuttals (each sees the other's argument)
        advocate_r2 = await self.advocate.argue(
            diff=diff, context=context,
            opponent_argument=critic_r1,
            instruction="Respond to the critic's concerns. Which are valid? Which are overblown?"
        )
        critic_r2 = await self.critic.argue(
            diff=diff, context=context,
            opponent_argument=advocate_r1,
            instruction="Respond to the advocate's points. What are they missing?"
        )

        # Judge evaluates the full debate
        decision = await self.judge.decide(
            diff=diff,
            debate_transcript={
                "advocate_opening": advocate_r1,
                "critic_opening": critic_r1,
                "advocate_rebuttal": advocate_r2,
                "critic_rebuttal": critic_r2,
            },
            pr_metadata={
                "author": pull_request.author,
                "files_changed": pull_request.files_changed,
                "test_coverage_delta": pull_request.coverage_delta,
                "ci_status": pull_request.ci_status,
            }
        )

        return decision

# Example output:
# ReviewDecision(
#   verdict="REQUEST_CHANGES",
#   blocking_issues=[
#     "Critic correctly identified race condition in cache invalidation (line 142-156). "
#     "The read-modify-write is not atomic and concurrent requests can lose updates.",
#     "Missing input validation on user_id parameter allows injection."
#   ],
#   advisory_issues=[
#     "Advocate's point about readability is valid — the nested ternary on line 89 "
#     "could be a named variable, but it's not blocking."
#   ],
#   dismissed_concerns=[
#     "Critic's concern about performance of list comprehension vs generator is "
#     "not relevant at this scale (< 100 items)."
#   ]
# )
```

### Effectiveness Metrics

```
Benchmark: 200 PRs reviewed by debate system AND by senior human reviewers

                    Single Agent    Debate System    Human Reviewer
Bugs found:            12              18               21
False positives:        8               4                2
Security issues:        3               6                7
Style-only feedback:   45%             15%              10%
Agreement with human:  68%             84%               —

Cost per review:       $0.12           $0.45            $75.00
Time per review:       30 seconds      2 minutes        25 minutes
```

---

## Supervisor-Worker: Customer Onboarding System

### Architecture with 5 Specialist Agents

```python
class CustomerOnboardingSupervisor:
    """
    Onboards enterprise customers with 5 specialist agents.
    Average onboarding: 2 hours (down from 3 days manual).

    Agents:
    1. Data Collector — gathers company info from APIs and forms
    2. Compliance Checker — verifies KYC/AML requirements
    3. Account Configurator — sets up accounts, permissions, integrations
    4. Training Content Generator — creates personalized onboarding materials
    5. Communication Agent — sends welcome emails, schedules calls
    """

    def __init__(self):
        self.agents = {
            "collector": DataCollectorAgent(model="gpt-4o-mini"),
            "compliance": ComplianceAgent(model="gpt-4o"),  # Higher capability for judgment
            "configurator": AccountConfigAgent(model="gpt-4o-mini"),
            "training": TrainingContentAgent(model="claude-sonnet-4-20250514"),
            "comms": CommunicationAgent(model="gpt-4o-mini"),
        }
        self.workflow_engine = WorkflowEngine()

    async def onboard(self, customer: CustomerApplication) -> OnboardingResult:
        workflow = self.workflow_engine.create(stages=[
            # Stage 1: Parallel data gathering
            Stage(
                name="data_collection",
                tasks=[
                    Task("collector", "gather_company_data", {"domain": customer.domain}),
                    Task("collector", "fetch_public_records", {"company_name": customer.name}),
                    Task("collector", "verify_contacts", {"contacts": customer.contacts}),
                ],
                parallel=True
            ),
            # Stage 2: Compliance (depends on Stage 1)
            Stage(
                name="compliance_check",
                tasks=[
                    Task("compliance", "kyc_verification", {"data": "$data_collection.output"}),
                    Task("compliance", "sanctions_screening", {"data": "$data_collection.output"}),
                    Task("compliance", "risk_assessment", {"data": "$data_collection.output"}),
                ],
                parallel=True,
                gate=Gate(
                    type="all_pass",
                    on_fail="escalate_to_human",
                    timeout_minutes=30
                )
            ),
            # Stage 3: Parallel setup (depends on compliance passing)
            Stage(
                name="account_setup",
                tasks=[
                    Task("configurator", "create_accounts", {
                        "plan": customer.plan,
                        "users": customer.initial_users
                    }),
                    Task("configurator", "setup_integrations", {
                        "requested_integrations": customer.integrations
                    }),
                    Task("training", "generate_materials", {
                        "industry": "$data_collection.output.industry",
                        "use_case": customer.primary_use_case,
                        "team_size": customer.team_size
                    }),
                ],
                parallel=True
            ),
            # Stage 4: Communication (depends on everything)
            Stage(
                name="welcome",
                tasks=[
                    Task("comms", "send_welcome_package", {
                        "customer": customer,
                        "accounts": "$account_setup.output.accounts",
                        "training_materials": "$account_setup.output.materials"
                    }),
                    Task("comms", "schedule_kickoff_call", {
                        "contacts": customer.contacts,
                        "availability": customer.preferred_times
                    }),
                ],
                parallel=True
            ),
        ])

        result = await self.workflow_engine.execute(workflow)
        return result
```

### Failure Handling in the Onboarding Pipeline

```python
class WorkflowEngine:
    async def execute_task(self, task: Task, context: dict) -> TaskResult:
        agent = self.agents[task.agent_name]
        retries = 0
        max_retries = 3

        while retries < max_retries:
            try:
                result = await asyncio.wait_for(
                    agent.execute(task.action, task.resolve_params(context)),
                    timeout=task.timeout_seconds or 120
                )

                # Validate output against expected schema
                if not task.validate_output(result):
                    raise InvalidOutputError(f"Agent output failed validation: {result}")

                return TaskResult(status="success", output=result)

            except asyncio.TimeoutError:
                retries += 1
                if retries >= max_retries:
                    return TaskResult(
                        status="timeout",
                        fallback=await self._execute_fallback(task, context)
                    )

            except AgentError as e:
                retries += 1
                if e.is_retryable and retries < max_retries:
                    await asyncio.sleep(2 ** retries)  # Exponential backoff
                    continue
                else:
                    # Non-retryable: try substitute agent or escalate
                    substitute = self._get_substitute_agent(task.agent_name)
                    if substitute:
                        return await self._execute_with_substitute(substitute, task, context)
                    else:
                        return TaskResult(status="failed", error=str(e), needs_human=True)
```

---

## Router-Specialist: Support Ticket Routing

### Implementation

```python
class SupportRouterSystem:
    """
    Routes 10,000+ tickets/day to specialized agents.
    Routing accuracy: 94% (measured by human override rate).
    """

    def __init__(self):
        self.router = RouterAgent(
            model="gpt-4o-mini",  # Fast, cheap for classification
            specialists={
                "billing": BillingAgent(model="gpt-4o-mini"),
                "technical": TechnicalAgent(model="gpt-4o"),  # Complex troubleshooting
                "account": AccountAgent(model="gpt-4o-mini"),
                "compliance": ComplianceAgent(model="gpt-4o"),  # High-stakes
                "general": GeneralAgent(model="gpt-4o-mini"),
            }
        )

    async def handle_ticket(self, ticket: SupportTicket) -> Resolution:
        # Step 1: Classify and route
        classification = await self.router.classify(ticket)
        # Returns: {
        #   "primary_category": "technical",
        #   "confidence": 0.87,
        #   "secondary_category": "billing",  # Sometimes tickets span categories
        #   "urgency": "high",
        #   "sentiment": "frustrated"
        # }

        # Step 2: Route based on confidence
        if classification.confidence > 0.8:
            specialist = self.router.specialists[classification.primary_category]
            response = await specialist.handle(ticket, classification)
        elif classification.confidence > 0.5:
            # Low confidence: try primary, have secondary on standby
            response = await specialist.handle(ticket, classification)
            if response.resolution_confidence < 0.6:
                # Escalate to secondary specialist
                secondary = self.router.specialists[classification.secondary_category]
                response = await secondary.handle(ticket, classification, previous_attempt=response)
        else:
            # Very low confidence: human routing
            response = Resolution(
                status="needs_human_routing",
                reason=f"Classification confidence too low: {classification.confidence}"
            )

        # Step 3: Quality check before sending
        if classification.urgency == "high" or ticket.customer_tier == "enterprise":
            response = await self._quality_review(response, ticket)

        return response

    async def _quality_review(self, response: Resolution, ticket: SupportTicket) -> Resolution:
        """
        For high-priority tickets, a review agent checks the response
        before it's sent to the customer.
        """
        review = await self.quality_agent.review(
            ticket=ticket,
            proposed_response=response,
            criteria=[
                "factual_accuracy",
                "completeness",
                "tone_appropriate",
                "no_hallucinated_steps",
                "includes_next_steps"
            ]
        )

        if review.passes:
            return response
        else:
            # Regenerate with feedback
            improved = await self.router.specialists[response.category].handle(
                ticket,
                additional_instruction=review.feedback
            )
            return improved
```

### Routing Performance

```
Monthly stats (30,000 tickets):
├── Billing: 8,200 (27%) — avg resolution: 2 min, automation rate: 89%
├── Technical: 11,400 (38%) — avg resolution: 8 min, automation rate: 71%
├── Account: 5,100 (17%) — avg resolution: 3 min, automation rate: 92%
├── Compliance: 2,100 (7%) — avg resolution: 15 min, automation rate: 45%
├── General: 2,400 (8%) — avg resolution: 4 min, automation rate: 85%
└── Human escalation: 800 (3%) — misrouted or complex edge cases

Routing accuracy by category:
├── Billing: 96% correct routing
├── Technical: 91% (hardest — overlaps with account issues)
├── Account: 95%
├── Compliance: 93%
└── General: 88% (catch-all has lowest precision)
```

---

## Planner-Executor Pattern

### Project Decomposition Agent

```python
class PlannerExecutorSystem:
    """
    A project planning agent decomposes complex requests into atomic tasks,
    then delegates to execution agents. Used for multi-step engineering work.

    Example: "Migrate our authentication from JWT to session-based with Redis"
    """

    def __init__(self):
        self.planner = PlannerAgent(
            model="gpt-4o",
            system_prompt="""You are a senior tech lead. Given a complex engineering task,
            decompose it into atomic, independently-executable steps.
            Each step should:
            - Be completable in one agent session
            - Have clear inputs and outputs
            - Specify success criteria
            - List file paths that will be modified
            - Estimate complexity (simple/medium/complex)
            Order steps by dependency (independent steps can be parallel)."""
        )
        self.executors = ExecutorPool(
            simple=Agent(model="gpt-4o-mini", max_tokens=4096),
            medium=Agent(model="claude-sonnet-4-20250514", max_tokens=8192),
            complex=Agent(model="gpt-4o", max_tokens=16384),
        )

    async def execute_project(self, task_description: str, codebase: Codebase) -> ProjectResult:
        # Step 1: Planner creates execution plan
        plan = await self.planner.create_plan(
            task=task_description,
            codebase_summary=codebase.get_structure(),
            relevant_files=codebase.find_relevant_files(task_description)
        )

        # Example plan output:
        # {
        #   "steps": [
        #     {
        #       "id": "1",
        #       "title": "Add Redis session store dependency",
        #       "complexity": "simple",
        #       "files": ["package.json", "docker-compose.yml"],
        #       "depends_on": [],
        #       "success_criteria": "Redis client configured, connection tested"
        #     },
        #     {
        #       "id": "2",
        #       "title": "Create session middleware",
        #       "complexity": "medium",
        #       "files": ["src/middleware/session.ts", "src/config/redis.ts"],
        #       "depends_on": ["1"],
        #       "success_criteria": "Middleware creates/validates sessions via Redis"
        #     },
        #     {
        #       "id": "3",
        #       "title": "Migrate auth routes from JWT to sessions",
        #       "complexity": "complex",
        #       "files": ["src/routes/auth.ts", "src/controllers/auth.ts"],
        #       "depends_on": ["2"],
        #       "success_criteria": "Login creates session, logout destroys it"
        #     },
        #     {
        #       "id": "4",
        #       "title": "Update protected route middleware",
        #       "complexity": "medium",
        #       "files": ["src/middleware/auth.ts"],
        #       "depends_on": ["2"],
        #       "success_criteria": "Protected routes validate session instead of JWT"
        #     },
        #     {
        #       "id": "5",
        #       "title": "Migration script and backward compatibility",
        #       "complexity": "complex",
        #       "files": ["src/scripts/migrate-sessions.ts"],
        #       "depends_on": ["3", "4"],
        #       "success_criteria": "Existing JWTs gracefully migrate to sessions"
        #     }
        #   ]
        # }

        # Step 2: Execute steps respecting dependencies
        completed = {}
        execution_order = self._topological_sort(plan["steps"])

        for batch in execution_order:
            # Each batch is a set of independent steps
            results = await asyncio.gather(*[
                self._execute_step(step, completed, codebase)
                for step in batch
            ])

            for step, result in zip(batch, results):
                if result.status == "failed":
                    # Planner re-evaluates: retry, modify plan, or abort
                    recovery = await self.planner.handle_failure(
                        failed_step=step,
                        error=result.error,
                        completed_steps=completed,
                        remaining_steps=self._get_remaining(plan, completed)
                    )
                    if recovery.action == "retry_modified":
                        result = await self._execute_step(
                            recovery.modified_step, completed, codebase
                        )
                    elif recovery.action == "abort":
                        return ProjectResult(status="aborted", reason=recovery.reason)

                completed[step["id"]] = result

        return ProjectResult(status="completed", steps=completed)

    async def _execute_step(self, step: dict, context: dict, codebase: Codebase):
        """Select executor based on complexity and execute."""
        executor = self.executors.get(step["complexity"])
        relevant_code = codebase.read_files(step["files"])
        dependency_outputs = {
            dep_id: context[dep_id].output
            for dep_id in step["depends_on"]
            if dep_id in context
        }

        return await executor.execute(
            instruction=step["title"],
            code_context=relevant_code,
            dependency_context=dependency_outputs,
            success_criteria=step["success_criteria"]
        )
```

---

## Multi-Agent Communication Patterns

### Pattern Comparison

```python
# Pattern 1: Message Passing (Agent-to-Agent via Queue)
class MessagePassingArchitecture:
    """
    Agents communicate through typed messages on a shared bus.
    Best for: Loosely coupled agents, event-driven workflows, high throughput.
    Drawback: Debugging is hard (messages fly everywhere), ordering issues.

    Performance:
    - Latency: 5-15ms per message hop
    - Throughput: 10K messages/second
    - Memory: Low (messages are transient)
    """

    def __init__(self):
        self.bus = MessageBus(backend="redis_streams")

    async def agent_loop(self, agent: Agent):
        async for message in self.bus.subscribe(agent.input_topics):
            result = await agent.process(message)
            if result.output_messages:
                for msg in result.output_messages:
                    await self.bus.publish(msg.topic, msg)


# Pattern 2: Shared State (Blackboard Pattern)
class SharedStateArchitecture:
    """
    All agents read/write to a shared state object.
    Best for: Tightly coordinated workflows, iterative refinement.
    Drawback: Race conditions, state can grow unbounded, hard to scale.

    Performance:
    - Latency: 1-3ms per state read/write
    - Throughput: Limited by lock contention
    - Memory: High (full state in memory)
    """

    def __init__(self):
        self.state = SharedState(backend="redis_json")
        self.lock = DistributedLock()

    async def agent_step(self, agent: Agent):
        async with self.lock.acquire(agent.state_keys):
            current_state = await self.state.read(agent.state_keys)
            result = await agent.process(current_state)
            await self.state.write(result.state_updates)


# Pattern 3: Event-Driven (Pub/Sub with Event Sourcing)
class EventDrivenArchitecture:
    """
    Agents emit events; other agents react to events they care about.
    Best for: Audit trails, replay capability, microservice-style agents.
    Drawback: Eventual consistency, complex event schemas, debugging.

    Performance:
    - Latency: 10-50ms (event processing + reaction)
    - Throughput: 50K events/second
    - Memory: Moderate (event store grows, but agents are stateless)
    """

    def __init__(self):
        self.event_store = EventStore(backend="kafka")
        self.projections = {}

    async def emit(self, agent_id: str, event: Event):
        event.source = agent_id
        event.timestamp = datetime.utcnow()
        await self.event_store.append(event)
        # Subscribers are notified asynchronously

    async def react(self, agent: Agent, event_types: list[str]):
        async for event in self.event_store.subscribe(event_types):
            reaction = await agent.react(event)
            if reaction:
                await self.emit(agent.id, reaction)
```

### When to Use Each

| Criteria | Message Passing | Shared State | Event-Driven |
|----------|----------------|--------------|--------------|
| Agents need full context | No | Yes | No |
| Need audit trail | No | No | Yes |
| Agents are stateless | Yes | No | Yes |
| Low latency critical | Maybe | Yes | No |
| Scale to 50+ agents | Yes | Hard | Yes |
| Debugging ease | Medium | Easy | Hard |
| Best for | Pipeline flows | Iterative refinement | Reactive systems |

---

## Failure Handling in Multi-Agent Pipelines

### Real Scenario: 5-Agent Document Processing Pipeline

```python
class DocumentProcessingPipeline:
    """
    Pipeline: Extract → Classify → Enrich → Validate → Store
    What happens when agent 3 (Enrich) fails?
    """

    FAILURE_STRATEGIES = {
        "extract": {
            "retry": 3,
            "substitute": "fallback_extractor",  # Simpler regex-based extractor
            "on_total_failure": "dead_letter_queue"
        },
        "classify": {
            "retry": 2,
            "substitute": "rule_based_classifier",
            "on_total_failure": "classify_as_unknown_and_continue"
        },
        "enrich": {
            "retry": 2,
            "substitute": None,  # No substitute available
            "on_total_failure": "skip_enrichment_and_continue",
            "degradation_mode": "partial_output_acceptable"
        },
        "validate": {
            "retry": 1,
            "substitute": "basic_schema_validator",
            "on_total_failure": "escalate_to_human"
        },
        "store": {
            "retry": 5,  # Transient DB errors are common
            "substitute": "backup_store",
            "on_total_failure": "dead_letter_queue_with_alert"
        }
    }

    async def process_with_resilience(self, document: Document) -> PipelineResult:
        context = {"document": document, "degraded": False}

        for stage_name in ["extract", "classify", "enrich", "validate", "store"]:
            agent = self.agents[stage_name]
            strategy = self.FAILURE_STRATEGIES[stage_name]
            result = None

            # Try primary agent with retries
            for attempt in range(strategy["retry"]):
                try:
                    result = await asyncio.wait_for(
                        agent.process(context),
                        timeout=30
                    )
                    if result.is_valid():
                        break
                except (AgentError, asyncio.TimeoutError) as e:
                    self.metrics.record_failure(stage_name, attempt, str(e))
                    if attempt < strategy["retry"] - 1:
                        await asyncio.sleep(2 ** attempt)

            # If primary failed, try substitute
            if result is None or not result.is_valid():
                if strategy.get("substitute"):
                    substitute = self.agents[strategy["substitute"]]
                    try:
                        result = await substitute.process(context)
                        context["degraded"] = True
                    except Exception:
                        result = None

            # If all attempts failed, apply total failure strategy
            if result is None or not result.is_valid():
                action = strategy["on_total_failure"]

                if action == "dead_letter_queue":
                    await self.dlq.send(document, stage=stage_name)
                    return PipelineResult(status="failed", stage=stage_name)

                elif action == "skip_enrichment_and_continue":
                    context["enrichment"] = {"status": "skipped"}
                    context["degraded"] = True
                    continue

                elif action == "classify_as_unknown_and_continue":
                    context["classification"] = {"category": "unknown", "confidence": 0}
                    context["degraded"] = True
                    continue

                elif action == "escalate_to_human":
                    await self.human_queue.send(document, context, stage_name)
                    return PipelineResult(status="needs_human", stage=stage_name)

            else:
                context[stage_name] = result.output

        return PipelineResult(
            status="completed" if not context["degraded"] else "completed_degraded",
            output=context
        )
```

---

## Agent Orchestration at Scale: 50+ Agent Types

### Registry and Capability Management

```python
class AgentRegistry:
    """
    Manages 50+ agent types with different capabilities, costs, and reliability.
    Acts as a service mesh for agents.
    """

    def __init__(self):
        self.agents = {}
        self.metrics = AgentMetricsCollector()

    def register(self, agent_config: AgentConfig):
        self.agents[agent_config.id] = RegisteredAgent(
            config=agent_config,
            health=HealthStatus.UNKNOWN,
            metrics=AgentMetrics()
        )

    def select_agent(self, capability: str, constraints: SelectionConstraints) -> str:
        """
        Select best agent for a capability given constraints.
        Considers: cost, latency, reliability, current load.
        """
        candidates = [
            a for a in self.agents.values()
            if capability in a.config.capabilities
            and a.health == HealthStatus.HEALTHY
        ]

        if not candidates:
            raise NoAgentAvailableError(f"No healthy agent for: {capability}")

        # Score candidates
        scored = []
        for agent in candidates:
            score = self._score_agent(agent, constraints)
            scored.append((score, agent))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1].config.id

    def _score_agent(self, agent: RegisteredAgent, constraints: SelectionConstraints) -> float:
        """
        Multi-criteria scoring:
        - Cost weight (default 0.3): prefer cheaper agents
        - Latency weight (default 0.3): prefer faster agents
        - Reliability weight (default 0.3): prefer more reliable agents
        - Load weight (default 0.1): prefer less loaded agents
        """
        m = agent.metrics

        cost_score = 1.0 - (m.avg_cost_per_call / constraints.max_cost_per_call)
        latency_score = 1.0 - (m.p95_latency_ms / constraints.max_latency_ms)
        reliability_score = m.success_rate_7d
        load_score = 1.0 - (m.current_concurrency / agent.config.max_concurrency)

        return (
            constraints.cost_weight * max(0, cost_score) +
            constraints.latency_weight * max(0, latency_score) +
            constraints.reliability_weight * reliability_score +
            constraints.load_weight * max(0, load_score)
        )

# Example registry at scale:
# ┌──────────────────────┬──────────┬─────────┬───────────┬──────────┐
# │ Agent Type           │ Cost/Call│ p95 (ms)│ Reliability│ Instances│
# ├──────────────────────┼──────────┼─────────┼───────────┼──────────┤
# │ summarizer-gpt4o     │ $0.03   │ 2100    │ 99.2%     │ 4        │
# │ summarizer-mini      │ $0.004  │ 800     │ 98.8%     │ 8        │
# │ code-reviewer        │ $0.08   │ 4500    │ 97.5%     │ 2        │
# │ sql-generator        │ $0.02   │ 1200    │ 96.1%     │ 3        │
# │ classifier-fast      │ $0.001  │ 200     │ 99.5%     │ 12       │
# │ compliance-checker   │ $0.05   │ 3000    │ 99.8%     │ 2        │
# │ data-extractor       │ $0.01   │ 900     │ 98.3%     │ 6        │
# │ ...48 more types...  │         │         │           │          │
# └──────────────────────┴──────────┴─────────┴───────────┴──────────┘
```

---

## Multi-Agent Evaluation

### System-Level vs Agent-Level Metrics

```python
class MultiAgentEvaluator:
    """
    Problem: Individual agents score 90%+ on their tasks,
    but the overall system only achieves 72% end-to-end success.
    Root cause: Coordination failures, context loss, error propagation.

    This evaluator measures SYSTEM performance, not just agent performance.
    """

    def evaluate_end_to_end(self, test_cases: list[TestCase]) -> SystemMetrics:
        results = []

        for case in test_cases:
            # Run the full multi-agent pipeline
            output = self.system.run(case.input)

            # Measure individual agent quality
            agent_scores = {}
            for agent_id, agent_output in output.agent_outputs.items():
                agent_scores[agent_id] = self._score_agent_output(
                    agent_output, case.expected_agent_outputs.get(agent_id)
                )

            # Measure system-level quality
            system_score = self._score_system_output(output.final_output, case.expected_output)

            # Measure coordination quality
            coordination_score = self._measure_coordination(output)

            results.append(EvalResult(
                agent_scores=agent_scores,
                system_score=system_score,
                coordination_score=coordination_score,
                latency=output.total_latency,
                cost=output.total_cost,
                error_propagation=self._detect_error_propagation(output)
            ))

        return self._aggregate(results)

    def _measure_coordination(self, output: SystemOutput) -> float:
        """
        Coordination quality metrics:
        1. Information loss: Did agent B receive all relevant info from agent A?
        2. Redundant work: Did two agents do the same thing?
        3. Conflict resolution: Were contradictions resolved correctly?
        4. Ordering efficiency: Were independent tasks parallelized?
        """
        scores = []

        # Information loss: compare what was produced vs what was consumed
        for handoff in output.agent_handoffs:
            produced = handoff.producer_output
            consumed = handoff.consumer_input
            info_preserved = self._measure_info_preservation(produced, consumed)
            scores.append(info_preserved)

        # Redundant work: detect duplicate API calls or computations
        all_tool_calls = [tc for agent in output.agents for tc in agent.tool_calls]
        unique_calls = set(self._normalize_call(tc) for tc in all_tool_calls)
        redundancy = 1.0 - (len(unique_calls) / len(all_tool_calls)) if all_tool_calls else 1.0
        scores.append(1.0 - redundancy)  # Lower redundancy = better score

        return statistics.mean(scores)

    def _detect_error_propagation(self, output: SystemOutput) -> list[ErrorChain]:
        """
        Detect when one agent's error cascades through the pipeline.
        Example: Extractor hallucinates a fact → Enricher builds on it →
                 Validator doesn't catch it → Wrong output stored.
        """
        chains = []
        for agent_output in output.agent_outputs.values():
            if agent_output.has_errors:
                # Trace which downstream agents consumed this error
                chain = self._trace_downstream(agent_output.errors, output)
                if len(chain) > 1:
                    chains.append(ErrorChain(
                        origin=agent_output.agent_id,
                        propagated_to=[c.agent_id for c in chain],
                        impact=self._assess_impact(chain)
                    ))
        return chains

# Real evaluation results:
# ┌─────────────────────┬────────────┬──────────────┬───────────────┐
# │ Metric              │ Agent Avg  │ System Level │ Gap           │
# ├─────────────────────┼────────────┼──────────────┼───────────────┤
# │ Accuracy            │ 91%        │ 72%          │ -19% (coord.) │
# │ Completeness        │ 88%        │ 68%          │ -20% (info loss)│
# │ Latency (p50)       │ 2s/agent   │ 12s total    │ Sequential    │
# │ Cost                │ $0.03/agent│ $0.18 total  │ 6 agents      │
# │ Error propagation   │ N/A        │ 23% of errors│ Cascade risk  │
# └─────────────────────┴────────────┴──────────────┴───────────────┘
```

---

## Cost Explosion and Control Strategies

### The Problem

```
Single-agent approach:
  User query → 1 LLM call → Response
  Cost: $0.03 average

Multi-agent approach (before optimization):
  User query → Router (1 call) → Planner (1 call) → 
  3 Executors (3 calls each = 9) → Validator (1 call) → 
  Synthesizer (1 call) = 13 LLM calls
  Cost: $0.39 average (13x increase!)

At 100K queries/day:
  Single: $3,000/day
  Multi: $39,000/day
  Monthly delta: $1,080,000 additional spend
```

### Control Strategies

```python
class CostAwareOrchestrator:
    """
    Strategies that reduced multi-agent costs from $0.39 to $0.11 per query
    while maintaining 95% of quality.
    """

    # Strategy 1: Tiered model selection per agent role
    MODEL_TIERS = {
        "router": "gpt-4o-mini",        # $0.15/1M tokens — simple classification
        "planner": "gpt-4o",             # $2.50/1M tokens — needs reasoning
        "executor_simple": "gpt-4o-mini", # Simple tasks don't need GPT-4
        "executor_complex": "claude-sonnet-4-20250514",  # Complex reasoning
        "validator": "gpt-4o-mini",       # Schema validation is simple
        "synthesizer": "gpt-4o",          # Final output quality matters
    }
    # Savings: 45% cost reduction vs using GPT-4o for everything

    # Strategy 2: Early termination
    async def execute_with_early_termination(self, query: str):
        """Skip agents when confidence is already high."""
        router_result = await self.router.classify(query)

        if router_result.confidence > 0.95 and router_result.is_simple:
            # Simple query: skip planner, use single executor
            return await self.executors["simple"].handle(query)
            # Cost: $0.005 instead of $0.39

        if router_result.confidence > 0.8:
            # Medium complexity: skip planner, use 1 executor + validator
            result = await self.executors["medium"].handle(query)
            if await self.validator.is_valid(result):
                return result
            # Cost: $0.04 instead of $0.39

        # Complex: full pipeline
        return await self.full_pipeline(query)
        # Cost: $0.39

    # Strategy 3: Caching intermediate results
    async def execute_with_caching(self, query: str):
        """Cache agent outputs for similar queries."""
        # Semantic cache: if a very similar query was processed recently,
        # reuse intermediate agent outputs
        cache_key = await self.semantic_cache.find_similar(query, threshold=0.95)
        if cache_key:
            cached = self.semantic_cache.get(cache_key)
            # Only re-run the final synthesis with the new query
            return await self.synthesizer.synthesize(query, cached.intermediate_results)
            # Cost: $0.03 instead of $0.39 (reuses all intermediate work)

    # Strategy 4: Batch similar queries
    async def batch_process(self, queries: list[str]):
        """Group similar queries and process them together."""
        clusters = self.cluster_queries(queries, max_cluster_size=10)
        results = []
        for cluster in clusters:
            # One planner call for the cluster instead of N calls
            shared_plan = await self.planner.plan_batch(cluster)
            # Execute once, adapt output per query
            shared_result = await self.executor.execute(shared_plan)
            for query in cluster:
                adapted = await self.adapter.adapt(shared_result, query)
                results.append(adapted)
        # Cost reduction: ~60% for queries with >50% semantic overlap

    # Strategy 5: Budget-aware execution
    async def execute_within_budget(self, query: str, max_budget: float = 0.20):
        """Hard budget cap per query. Degrade gracefully if budget exceeded."""
        spent = 0.0
        context = {}

        for stage in self.pipeline_stages:
            estimated_cost = self._estimate_stage_cost(stage, context)
            if spent + estimated_cost > max_budget:
                # Skip remaining stages, synthesize with what we have
                return await self.synthesizer.synthesize_partial(
                    query, context, skipped_stages=self.pipeline_stages[stage:]
                )
            result = await stage.execute(context)
            spent += result.actual_cost
            context[stage.name] = result

        return context["final"]
```

### Cost Breakdown After Optimization

```
Before optimization: $0.39/query average
After optimization:  $0.11/query average (72% reduction)

Breakdown of savings:
├── Tiered models: -$0.12 (31% of savings)
├── Early termination: -$0.09 (23% of savings) — 40% of queries are simple
├── Semantic caching: -$0.04 (10% of savings) — 15% cache hit rate
├── Budget caps: -$0.03 (8% of savings) — prevents runaway complex queries
└── Total saved: $0.28/query

At 100K queries/day: $11,000/day (down from $39,000)
Monthly savings: $840,000
```

---

## Human-in-the-Loop in Multi-Agent Pipelines

### Checkpoint Design

```python
class HumanCheckpointOrchestrator:
    """
    Inserts human review at strategic points in multi-agent pipelines.
    Key principle: Interrupt only when the cost of an error exceeds
    the cost of human review time.
    """

    CHECKPOINT_RULES = {
        # Checkpoint before external actions (irreversible)
        "before_external_action": {
            "trigger": lambda output: output.has_external_side_effects,
            "examples": ["sending email", "creating account", "processing payment"],
            "timeout_minutes": 60,
            "on_timeout": "reject"  # Safe default for irreversible actions
        },
        # Checkpoint on low confidence
        "low_confidence": {
            "trigger": lambda output: output.confidence < 0.7,
            "examples": ["ambiguous classification", "uncertain extraction"],
            "timeout_minutes": 30,
            "on_timeout": "proceed_with_flag"  # Mark as unverified
        },
        # Checkpoint on high-value decisions
        "high_value": {
            "trigger": lambda output: output.estimated_impact_dollars > 10000,
            "examples": ["contract approval", "large refund", "access grant"],
            "timeout_minutes": 120,
            "on_timeout": "escalate_to_manager"
        },
        # Checkpoint on policy violations detected
        "policy_violation": {
            "trigger": lambda output: output.policy_flags,
            "examples": ["PII detected", "bias detected", "compliance risk"],
            "timeout_minutes": 15,
            "on_timeout": "reject"
        }
    }

    async def execute_with_checkpoints(self, pipeline: Pipeline, input_data: dict):
        context = {"input": input_data}

        for stage in pipeline.stages:
            result = await stage.agent.execute(context)

            # Check if any checkpoint rule triggers
            checkpoint = self._evaluate_checkpoints(result, stage)

            if checkpoint:
                # Pause pipeline, notify human
                review_request = HumanReviewRequest(
                    stage=stage.name,
                    agent_output=result,
                    checkpoint_reason=checkpoint.reason,
                    context_summary=self._summarize_context(context),
                    suggested_action=result.suggested_action,
                    alternatives=result.alternative_actions,
                    deadline=datetime.now() + timedelta(minutes=checkpoint.timeout_minutes)
                )

                human_decision = await self.human_review_queue.submit_and_wait(
                    review_request,
                    timeout=timedelta(minutes=checkpoint.timeout_minutes)
                )

                if human_decision is None:  # Timeout
                    human_decision = self._handle_timeout(checkpoint)

                if human_decision.action == "approve":
                    context[stage.name] = result
                elif human_decision.action == "reject":
                    return PipelineResult(status="rejected_by_human", stage=stage.name)
                elif human_decision.action == "modify":
                    # Human provided corrections; re-run stage with corrections
                    result = await stage.agent.execute(
                        context, corrections=human_decision.corrections
                    )
                    context[stage.name] = result
                elif human_decision.action == "override":
                    # Human provides the output directly
                    context[stage.name] = human_decision.override_output
            else:
                context[stage.name] = result

        return PipelineResult(status="completed", output=context)
```

### Where to Place Checkpoints (Decision Framework)

```
                    ┌─────────────────────────────────────┐
                    │  Is the action reversible?           │
                    └──────────┬──────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │        YES          │──→ No checkpoint needed (can undo)
                    └─────────────────────┘
                               │ NO
                    ┌──────────▼──────────────────────────┐
                    │  Is agent confidence > 95%?          │
                    └──────────┬──────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │        YES          │──→ No checkpoint (high confidence + tested)
                    └─────────────────────┘
                               │ NO
                    ┌──────────▼──────────────────────────┐
                    │  Is impact < $100?                   │
                    └──────────┬──────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │        YES          │──→ Log-only checkpoint (review async)
                    └─────────────────────┘
                               │ NO
                    ┌──────────▼──────────────────────────┐
                    │  BLOCKING CHECKPOINT REQUIRED        │
                    │  Human must approve before proceeding│
                    └─────────────────────────────────────┘

Real-world checkpoint frequency:
├── Customer onboarding pipeline: 1 checkpoint (compliance gate) out of 12 stages
├── Due diligence system: 3 checkpoints (legal findings, financial red flags, final report)
├── Code deployment pipeline: 2 checkpoints (pre-merge review, pre-production deploy)
├── Support ticket handling: 0 checkpoints for tier 1, 1 for refunds > $500
└── Content generation: 1 checkpoint (before publishing externally)

Impact on pipeline latency:
├── Without checkpoints: 4 minutes end-to-end
├── With async checkpoints: 4 minutes (human reviews in parallel)
├── With 1 blocking checkpoint: 4 min + avg 12 min human review = 16 min
├── With 3 blocking checkpoints: 4 min + avg 36 min human review = 40 min
└── Optimization: Batch checkpoint reviews, pre-approve low-risk patterns
```

---

## Key Takeaways

1. **Supervisor-worker** excels when tasks have clear decomposition and quality gates matter more than speed
2. **Debate-and-judge** catches 34% more issues than single-agent review — use for high-stakes decisions
3. **Router-specialist** scales to 10K+ requests/day with 94% routing accuracy using cheap classification models
4. **Planner-executor** enables complex multi-step tasks but needs robust failure recovery
5. **Message passing** scales best for 50+ agents; shared state is simpler but limits scale
6. **Failure handling** requires per-stage strategies — not every failure should retry or escalate
7. **Agent registries** with capability scoring enable dynamic agent selection at scale
8. **System-level evaluation** reveals coordination failures invisible at agent level (19% accuracy gap)
9. **Cost control** through tiered models + early termination reduces spend by 72%
10. **Human checkpoints** belong at irreversible, high-value, or low-confidence decision points only
