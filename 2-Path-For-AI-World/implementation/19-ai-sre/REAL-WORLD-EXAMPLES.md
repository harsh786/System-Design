# AI SRE — Real-World Examples

## Case Study 1: Defining SLOs for AI Services at an AI-First Company

### Company Context: "NovaMind" — Series C AI Writing Assistant (12M MAU)

NovaMind operates an AI writing assistant powered by GPT-4 class models with RAG for enterprise knowledge. Their SRE team spent 6 weeks defining SLOs that capture AI-specific reliability dimensions.

### The Three Pillars of AI SLOs

```yaml
# novamind-slo-definitions.yaml
service: writing-assistant-v3
owner: platform-team
review_cadence: monthly

slos:
  # PILLAR 1: Availability SLO
  - name: "Service Availability"
    description: "Requests that receive a non-error response within timeout"
    sli:
      type: availability
      good_event: "response_code != 5xx AND response_time < 30s"
      valid_event: "all incoming requests excluding health checks"
    objective: 99.5%
    window: 30d_rolling
    error_budget: 0.5% = ~21.6 minutes of downtime per 30 days
    rationale: |
      We accept lower availability than traditional SaaS (99.9%) because:
      - Model provider outages are outside our control
      - Users tolerate brief unavailability better than bad quality
      - Fallback to cached/degraded mode counts as "available"

  # PILLAR 2: Quality SLO
  - name: "Response Quality — Groundedness"
    description: "Responses that are grounded in provided context"
    sli:
      type: quality
      measurement: |
        Sample 5% of responses through automated groundedness evaluator.
        Score 0-1. Good event = score >= 0.80.
      good_event: "groundedness_score >= 0.80"
      valid_event: "all sampled responses for RAG-enabled queries"
    objective: 92%
    window: 7d_rolling
    error_budget: 8% of responses can fall below quality bar
    rationale: |
      Quality SLOs are harder because:
      - Measurement is probabilistic (evaluator has ~3% disagreement with humans)
      - "Quality" varies by use case (creative writing vs. legal summaries)
      - We chose 7d window because quality regressions must be caught fast

  - name: "Response Quality — Harmlessness"
    description: "Responses free from harmful, biased, or toxic content"
    sli:
      type: safety
      measurement: "All responses pass through safety classifier. Good = score < 0.3"
      good_event: "safety_classifier_score < 0.3"
      valid_event: "all responses served to users"
    objective: 99.95%
    window: 30d_rolling
    error_budget: 0.05% = ~500 harmful responses per 1M requests
    rationale: |
      Strictest SLO. A single viral harmful response can cause:
      - Brand damage worth millions
      - Regulatory scrutiny
      - User trust erosion that takes months to recover

  # PILLAR 3: Latency SLO
  - name: "Time to First Token"
    description: "Time from request receipt to first streamed token"
    sli:
      type: latency
      good_event: "ttft < 2000ms"
      valid_event: "all streaming requests"
    objective: 95%
    window: 30d_rolling
    percentile_targets:
      p50: 800ms
      p95: 2000ms
      p99: 5000ms

  - name: "End-to-End Latency"
    description: "Time from request to complete response"
    sli:
      type: latency
      good_event: "total_latency < 15s for responses under 500 tokens"
      valid_event: "all non-streaming requests with output < 500 tokens"
    objective: 90%
    window: 30d_rolling
```

### How They Chose These Numbers

| SLO | Initial Proposal | After 4 Weeks Data | Final |
|-----|-----------------|-------------------|-------|
| Availability | 99.9% | Baseline was 99.3% due to provider outages | 99.5% |
| Groundedness | 95% | Evaluator showed 89% baseline | 92% |
| Harmlessness | 99.99% | Too tight — burned budget on false positives | 99.95% |
| TTFT P95 | 1000ms | RAG retrieval alone took 600ms P95 | 2000ms |

### Key Insight: SLO Dependencies

```
Quality SLO depends on:
├── Embedding model freshness (stale embeddings → irrelevant retrieval → low groundedness)
├── Vector DB recall accuracy (if recall < 0.85, groundedness SLO is impossible)
├── Model provider quality (GPT-4 vs GPT-3.5 fallback degrades quality by ~15%)
└── Prompt template correctness (a bad prompt deploy can tank quality instantly)

Latency SLO depends on:
├── Model provider latency (70% of total latency)
├── Vector DB query time (15% of total latency)
├── Network hops (10%)
└── Pre/post processing (5%)
```

---

## Case Study 2: Incident Response — AI Service Producing Harmful Content at Scale

### Timeline: The "NovaMind Jailbreak Incident"

**Context:** A coordinated group discovered a prompt injection that bypassed NovaMind's safety guardrails, causing the system to generate instructions for illegal activities when given specific enterprise document formatting.

```
DAY 0 — Thursday

14:23 UTC — Safety classifier alert fires: "Harmful content rate spike"
             Normal: 0.02% | Current: 0.8% | Threshold: 0.1%
             PagerDuty pages on-call AI SRE (L1)

14:25 UTC — L1 acknowledges. Opens incident channel #inc-2024-0847
             Checks dashboard: spike correlates with requests from 47 distinct users
             Pattern: All requests contain specific document template prefix

14:28 UTC — L1 escalates to L2 (ML Safety Engineer on-call)
             Severity upgraded: SEV-1 (harmful content actively being served)

14:31 UTC — L2 confirms: Prompt injection bypasses system prompt guardrails
             The attack exploits instruction-following behavior when text is
             formatted as "INTERNAL POLICY DOCUMENT: ..."

14:35 UTC — DECISION: Deploy emergency input filter
             Action: Regex + embedding similarity filter blocks requests
             matching attack pattern signature
             Impact: ~0.3% false positive rate on legitimate enterprise docs

14:37 UTC — Emergency filter deployed via feature flag (no redeploy needed)
             Harmful content rate drops from 0.8% to 0.04%

14:42 UTC — Incident commander (VP Eng) joins. Customer comms team alerted.

15:00 UTC — Full attack pattern analysis complete. 312 harmful responses served
             over 35-minute window. 47 users affected, 12 were attackers,
             35 were legitimate users who received degraded (blocked) responses.

15:30 UTC — Customer-facing status page updated:
             "We identified and mitigated a content safety issue. Some users
              may have experienced blocked requests. Investigation ongoing."

16:00 UTC — ML team deploys updated safety classifier trained on attack pattern
             False positive rate of emergency filter reduced from 0.3% to 0.01%

18:00 UTC — Emergency filter replaced with proper ML-based detection
             Incident moved to monitoring phase

DAY 1 — Friday

09:00 UTC — Review all 312 harmful responses. Categorize severity:
             - 280: Mildly inappropriate (policy violations, not dangerous)
             - 28: Concerning (could enable harm if followed)
             - 4: Severe (specific dangerous instructions)

10:00 UTC — 4 severe responses traced. 2 users were attackers (accounts suspended).
             2 were legitimate users who received harmful content unprompted
             (the attack was triggered by adjacent request contamination)

11:00 UTC — Direct outreach to 2 affected legitimate users with apology
             and explanation

14:00 UTC — Incident closed. Postmortem scheduled for Monday.
```

### Prevention Measures Implemented

```python
# Multi-layer defense deployed after incident

class HardenedSafetyPipeline:
    """
    Defense-in-depth for content safety.
    Each layer operates independently — single layer failure doesn't expose users.
    """

    def __init__(self):
        self.layers = [
            InputSanitizer(),          # Layer 1: Strip injection patterns
            PromptIsolation(),         # Layer 2: Separate user input from instructions
            OutputClassifier(),        # Layer 3: Real-time output classification
            StreamingMonitor(),        # Layer 4: Mid-stream abort if safety degrades
            PosthocAudit(),           # Layer 5: Async audit of all responses
        ]

    async def process(self, request):
        # Pre-generation safety
        sanitized = self.layers[0].sanitize(request.input)
        isolated_prompt = self.layers[1].isolate(sanitized, request.system_prompt)

        # Generation with streaming monitor
        response_stream = await self.generate(isolated_prompt)
        monitored_stream = self.layers[3].wrap(response_stream)

        # Real-time output check (every 50 tokens)
        async for chunk in monitored_stream:
            safety_score = await self.layers[2].score_incremental(chunk)
            if safety_score > 0.7:  # High confidence harmful
                await self.abort_and_replace(request, chunk)
                return SAFE_FALLBACK_RESPONSE

        # Async post-hoc (doesn't block response, but flags for review)
        self.layers[4].queue_audit(request, response_stream.full_text)

        return response_stream
```

---

## Case Study 3: SLO Design for RAG Systems

### Production RAG SLO Dashboard (Real Numbers from a Legal AI Platform)

```yaml
service: legal-research-rag
team: ai-platform
measurement_infrastructure: 
  - OpenTelemetry traces for latency
  - LLM-as-judge for quality (GPT-4 evaluates 10% sample)
  - Human eval on 1% sample (calibrates LLM-judge monthly)

slos:
  availability:
    target: 99.5%
    current_30d: 99.72%
    budget_remaining: 68%
    measurement: "Non-5xx responses within 30s timeout"

  latency_ttft:
    target_p95: 3000ms
    current_p95: 2340ms
    budget_remaining: 82%
    breakdown:
      embedding_generation: 120ms (p95)
      vector_search: 280ms (p95)
      reranking: 450ms (p95)
      llm_first_token: 1200ms (p95)
      overhead: 290ms (p95)

  groundedness:
    target: 85% of responses score >= 0.85 on groundedness
    current_7d: 88.3%
    budget_remaining: 41%  # ← concerning, quality tends to drift
    measurement: |
      GPT-4 judge scores each response on 0-1 scale:
      "Given ONLY the retrieved context, is the response supported?"
      Score >= 0.85 = grounded. Sample: 10% of all responses.
    alert_threshold: budget_remaining < 30%

  hallucination_rate:
    target: < 2% of responses contain fabricated citations/facts
    current_7d: 1.3%
    budget_remaining: 55%
    measurement: |
      Automated checker verifies:
      1. All cited case numbers exist in database
      2. All quoted text appears verbatim in source
      3. All stated dates/figures match source documents
    severity: "Any single hallucinated legal citation is a SEV-2"

  retrieval_relevance:
    target: "Top-5 retrieved docs contain answer for 90% of queries"
    current_7d: 91.7%
    measurement: "Human eval on 1% sample + LLM-judge on 10% sample"
```

### Error Budget Burn Rate Alerts

```python
# Real alert configuration for RAG quality SLOs

ALERT_CONFIGS = {
    "groundedness_fast_burn": {
        "condition": "error_budget_consumption_rate > 10x normal over 1 hour",
        "severity": "SEV-2",
        "action": "Page ML on-call. Likely model or retrieval regression.",
        "example_trigger": "Deployed new embedding model that retrieves less relevant docs"
    },
    "groundedness_slow_burn": {
        "condition": "error_budget_consumption_rate > 2x normal over 24 hours",
        "severity": "SEV-3",
        "action": "Ticket for next business day. Likely gradual drift.",
        "example_trigger": "Knowledge base grew 20% without reindexing"
    },
    "hallucination_any": {
        "condition": "hallucination_count > 5 in 1 hour",
        "severity": "SEV-2",
        "action": "Page ML on-call. Check prompt template, model version, retrieval.",
        "example_trigger": "Model provider silently upgraded minor version"
    },
    "hallucination_legal_citation": {
        "condition": "fabricated_citation_detected",
        "severity": "SEV-1",
        "action": "Page ML on-call AND legal team. Potential liability.",
        "example_trigger": "Model generated plausible but non-existent case number"
    }
}
```

---

## Case Study 4: Error Budget Management for AI Quality

### Team: "Atlas AI" — AI-Powered Customer Support (Fortune 500 Client)

**Scenario:** The team has a 30-day rolling quality error budget. They must balance shipping improvements (which risk quality regressions) against stability.

```
┌─────────────────────────────────────────────────────────────────┐
│                    ERROR BUDGET STATUS BOARD                      │
│                    Month: March 2025                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Quality SLO: 92% of responses score "helpful" by user feedback  │
│  Budget: 8% can be "not helpful"                                 │
│                                                                   │
│  Day 1-7:   ████████████████████░░░░ Budget: 78% remaining       │
│  Day 8-14:  █████████████░░░░░░░░░░░ Budget: 54% remaining       │
│  Day 15:    ████████████░░░░░░░░░░░░ Budget: 48% remaining  ⚠️   │
│  Day 16-21: █████████░░░░░░░░░░░░░░░ Budget: 35% remaining       │
│  Day 22:    ██████░░░░░░░░░░░░░░░░░░ Budget: 24% remaining  🔴   │
│                                                                   │
│  STATUS: DEPLOYMENT FREEZE ACTIVATED (Day 22)                    │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### The Error Budget Policy

```yaml
error_budget_policy:
  service: customer-support-ai
  slo: quality_helpfulness_92pct

  thresholds:
    green:  # Budget > 50%
      allowed_actions:
        - Deploy new model versions
        - A/B test experimental prompts (up to 20% traffic)
        - Enable new features behind feature flags
        - Run adversarial testing campaigns
      approval: Team lead sign-off

    yellow:  # Budget 25-50%
      allowed_actions:
        - Deploy only pre-validated model versions (eval score > baseline)
        - A/B tests limited to 5% traffic
        - No new features unless they improve quality metrics
      approval: Engineering manager sign-off
      additional: Root cause analysis on budget consumption required

    red:  # Budget < 25%
      allowed_actions:
        - ONLY bug fixes and quality improvements
        - All experiments halted
        - Rollback any recent changes that correlate with quality drop
        - Team allocation: 50% on quality recovery, 50% on normal work
      approval: VP Engineering sign-off for any deployment
      additional: |
        - Daily budget review standup
        - Mandatory postmortem on what consumed the budget
        - Consider tightening guardrails temporarily

    critical:  # Budget < 10%
      allowed_actions:
        - ONLY quality recovery work
        - Switch to most conservative model settings
        - Reduce traffic to AI system (route to human agents)
        - All hands on quality recovery
      approval: CTO approval for any change
      escalation: Executive team notified

  special_cases:
    model_provider_outage:
      description: "If budget burn is caused by model provider degradation"
      action: "Doesn't count against team's budget if provider SLA violated"
      process: "File provider incident, exclude affected time window"

    intentional_experiments:
      description: "Planned A/B tests that knowingly risk quality"
      action: "Pre-allocate budget slice (max 20% of remaining budget)"
      process: "Experiment proposal must include budget impact estimate"
```

### Real Decision Scenario

```
Date: March 15 (Budget at 48% — Yellow zone)

PROPOSAL: Deploy fine-tuned model that improves response quality by 8% on eval set
           but has unknown behavior on edge cases

DECISION PROCESS:
1. Offline eval: +8% quality on standard benchmark ✓
2. Shadow mode: Run on 100% traffic, compare but don't serve: +5% quality, 
   but 2 edge cases produced concerning outputs
3. Risk assessment: At 48% budget, we have room for ~4% quality degradation
   before hitting red zone. The 2 edge cases represent <0.1% of traffic.
4. Mitigation: Deploy with enhanced monitoring, auto-rollback if quality 
   drops >2% over 1 hour

OUTCOME: Deployed. Quality improved by 4.5% in production. Budget recovered to 62%.
```

---

## Case Study 5: AI-Specific Runbooks

### Runbook 1: Model Provider Outage

```yaml
runbook: model-provider-outage
trigger: "Provider API returns 5xx or timeout rate > 10% over 5 minutes"
severity: SEV-2 (auto-escalates to SEV-1 if >15 min)
last_updated: 2025-01-15
owner: ai-platform-team

diagnosis:
  step_1:
    action: "Check provider status page"
    urls:
      - "https://status.openai.com"
      - "https://status.anthropic.com"
    note: "Provider status pages often lag 5-10 min behind actual issues"

  step_2:
    action: "Confirm it's provider-side, not us"
    commands:
      - "curl -w '%{time_total}' https://api.openai.com/v1/models"
      - "Check: Is our API gateway healthy? (Grafana dashboard: ai-gateway-health)"
      - "Check: Are other customers reporting issues? (Twitter, DownDetector)"

  step_3:
    action: "Assess scope"
    questions:
      - "Which models are affected? (gpt-4 only? all models?)"
      - "Is it total outage or degraded performance?"
      - "What % of our traffic uses affected models?"

mitigation:
  automatic:
    - "Circuit breaker activates after 5 consecutive failures"
    - "Traffic routes to fallback model (Anthropic Claude if OpenAI down, vice versa)"
    - "If all providers down: serve from response cache (stale but functional)"

  manual_if_auto_fails:
    step_1: "Verify circuit breaker state: kubectl get configmap circuit-breaker-state"
    step_2: "Force fallback: kubectl set env deployment/ai-gateway FORCE_PROVIDER=anthropic"
    step_3: "If cache mode needed: kubectl scale deployment/cache-server --replicas=10"

  user_communication:
    - "Update status page within 10 min of detection"
    - "Template: 'We're experiencing degraded AI response quality due to an 
       upstream provider issue. Responses may be slower or generated by our 
       backup model. We're monitoring and will update within 30 minutes.'"

resolution:
  - "Provider recovers → circuit breaker auto-resets after 30s of healthy responses"
  - "Verify quality metrics return to baseline within 15 min of recovery"
  - "Close incident, file postmortem if duration > 30 min"

lessons_learned: |
  2024-08: OpenAI outage lasted 4 hours. Our fallback to Claude worked but 
  quality SLO dropped 3% because prompts were optimized for GPT-4.
  ACTION: Maintain provider-agnostic prompts or provider-specific prompt variants.
```

### Runbook 2: Quality Degradation Detected

```yaml
runbook: quality-degradation-detected
trigger: "Quality score drops > 5% over 2-hour window OR hallucination rate > 3%"
severity: SEV-2
owner: ml-quality-team

diagnosis:
  step_1:
    action: "Identify when degradation started"
    tool: "Grafana dashboard: ai-quality-metrics"
    correlate_with:
      - "Recent deployments (last 24h)"
      - "Model provider changes (check provider changelog)"
      - "Knowledge base updates (last indexing job)"
      - "Traffic pattern changes (new user segment?)"

  step_2:
    action: "Isolate the component"
    tests:
      retrieval_test: |
        Run standard eval queries against vector DB.
        If recall dropped: retrieval problem.
        Command: python scripts/eval_retrieval.py --suite=standard-50
      
      generation_test: |
        Run standard prompts with known-good context directly to model.
        If quality dropped: model/prompt problem.
        Command: python scripts/eval_generation.py --provider=current --suite=quality-30
      
      end_to_end_test: |
        Run full pipeline eval.
        Command: python scripts/eval_e2e.py --suite=regression-100

  step_3:
    action: "Check for silent model updates"
    detail: |
      Providers sometimes update models without notice.
      Check: model response fingerprint (avg token count, vocabulary distribution)
      Command: python scripts/check_model_fingerprint.py --window=7d
      If fingerprint changed: likely silent model update.

mitigation:
  if_retrieval_degraded:
    - "Check embedding model version hasn't changed"
    - "Verify vector DB index health: python scripts/check_index.py"
    - "If recent reindex: rollback to previous index snapshot"

  if_generation_degraded:
    - "Rollback to last known-good prompt template version"
    - "If model update suspected: pin to specific model version/snapshot"
    - "Increase temperature guardrails (reduce from 0.7 to 0.3)"

  if_cause_unknown:
    - "Activate safe mode: use most conservative settings"
    - "Increase human-in-the-loop review to 20% of responses"
    - "Escalate to ML team for deep investigation"
```

### Runbook 3: Cost Spike Detected

```yaml
runbook: ai-cost-spike
trigger: "Hourly AI API spend > 2x 7-day average for same hour"
severity: SEV-3 (SEV-2 if > 5x)
owner: ai-platform-team

diagnosis:
  step_1:
    action: "Identify cost source"
    dashboard: "ai-cost-breakdown (by model, endpoint, customer, feature)"
    common_causes:
      - "Retry storm (failed requests retrying aggressively)"
      - "Prompt length explosion (context window stuffing)"
      - "Traffic spike (legitimate or attack)"
      - "Accidental loop (code bug calling API repeatedly)"
      - "New feature launch without cost estimation"

  step_2:
    action: "Check token usage patterns"
    query: |
      SELECT 
        feature_name,
        AVG(prompt_tokens) as avg_prompt,
        AVG(completion_tokens) as avg_completion,
        COUNT(*) as request_count,
        SUM(estimated_cost_usd) as total_cost
      FROM ai_requests
      WHERE timestamp > NOW() - INTERVAL 2 HOUR
      GROUP BY feature_name
      ORDER BY total_cost DESC

mitigation:
  immediate:
    - "Enable rate limiting if not already active"
    - "If retry storm: disable retries, fix circuit breaker"
    - "If single customer: apply per-customer rate limit"

  if_prompt_explosion:
    - "Check RAG retrieval: is it stuffing too many documents?"
    - "Verify context window truncation is working"
    - "Temporary: reduce max context from 128K to 32K tokens"

  if_traffic_spike:
    - "Verify traffic is legitimate (not attack/scraping)"
    - "Enable request queuing with backpressure"
    - "Scale down to cheaper model for overflow traffic"

  budget_protection:
    - "Hard spending cap: auto-disable non-critical AI features at $X/hour"
    - "Alert finance team if projected daily spend > 150% of budget"
```

### Runbook 4: Guardrail Bypass Detected

```yaml
runbook: guardrail-bypass
trigger: "Safety classifier detects harmful output that passed all input filters"
severity: SEV-1 (always — harmful content in production is critical)
owner: ml-safety-team + security-team

immediate_actions:
  within_5_minutes:
    - "Identify the bypass pattern from logs"
    - "Deploy emergency input filter (regex/embedding-based block)"
    - "Flag and review ALL responses from the last hour for same pattern"

  within_30_minutes:
    - "Quantify exposure: how many users saw harmful content?"
    - "Block identified attacker accounts"
    - "Notify legal team if content involves illegality/liability"
    - "Update status page if user-visible impact"

  within_2_hours:
    - "Train updated safety classifier on new attack pattern"
    - "Deploy in shadow mode, verify catch rate"
    - "Promote to production, remove emergency regex filter"

investigation:
  questions:
    - "Was this an intentional attack or accidental bypass?"
    - "Is this a known jailbreak technique or novel?"
    - "Which layer of our defense failed and why?"
    - "Are there related patterns that might also bypass?"

prevention:
  - "Add attack pattern to adversarial eval suite"
  - "Run red-team exercise on related patterns"
  - "Consider: does our system prompt need restructuring?"
  - "Review: are we using latest provider safety features?"
```

### Runbook 5: Vector Database Performance Degradation

```yaml
runbook: vector-db-lag
trigger: "Vector search P95 latency > 500ms (normal: 100ms) OR recall drops > 10%"
severity: SEV-3 (SEV-2 if impacting end-user latency SLO)
owner: data-platform-team

diagnosis:
  step_1:
    action: "Check vector DB cluster health"
    checks:
      - "Node status: are all replicas healthy?"
      - "Memory pressure: is the index fitting in RAM?"
      - "Recent index operations: reindexing, compaction, migration?"
      - "Query volume: sudden traffic spike?"

  step_2:
    action: "Profile slow queries"
    detail: |
      Check if specific query patterns are slow:
      - High-dimensional queries (embedding dimension mismatch?)
      - Queries hitting cold segments (recently added data not in cache?)
      - Filter queries (metadata filtering causing full scans?)

  step_3:
    action: "Check index health"
    commands:
      - "curl localhost:6333/collections/main/info  # Qdrant example"
      - "Verify: segment count, vector count, index status"
      - "Check: is index being rebuilt? (status: 'indexing')"

mitigation:
  if_memory_pressure:
    - "Scale up: add memory or nodes"
    - "Offload cold data to disk-backed segments"
    - "Reduce ef_search parameter (trades recall for speed)"

  if_index_issue:
    - "Wait for reindexing to complete if in progress"
    - "If corrupt: restore from last snapshot"
    - "Temporary: increase number of candidates (nprobe) to maintain recall"

  if_traffic_spike:
    - "Enable query caching for repeated similar queries"
    - "Add read replicas"
    - "Implement request coalescing for identical queries"

  user_impact_mitigation:
    - "Reduce top-k from 20 to 5 (faster, still functional)"
    - "Enable approximate search if exact search is slow"
    - "Fallback: use BM25 keyword search if vector search SLO breached"
```

---

## Case Study 6: Chaos Engineering for AI Systems

### "Operation Entropy" — NovaMind's Quarterly AI Chaos Day

```python
"""
AI Chaos Engineering Framework
Run quarterly to validate resilience assumptions.
Each experiment has a hypothesis, method, and blast radius limit.
"""

class AIChaosExperiments:
    
    EXPERIMENT_1 = {
        "name": "Model Provider Total Failure",
        "hypothesis": "When OpenAI API returns 503 for all requests, system falls "
                      "back to Anthropic within 5 seconds with < 10% quality degradation",
        "method": "Inject 503 responses at API gateway for OpenAI endpoints",
        "blast_radius": "10% of production traffic (canary deployment)",
        "duration": "15 minutes",
        "success_criteria": [
            "Fallback activates within 5 seconds",
            "User-facing error rate < 1%",
            "Quality score on fallback model >= 85% of primary",
            "No data loss (all requests eventually served)"
        ],
        "actual_results_2024_q3": {
            "fallback_activation_time": "3.2 seconds",
            "user_error_rate": "0.4%",
            "quality_on_fallback": "91% of primary (better than expected)",
            "data_loss": "0 requests lost",
            "surprise_finding": "Fallback model was 40% cheaper — led to cost optimization project"
        }
    }

    EXPERIMENT_2 = {
        "name": "Embedding Model Returns Garbage",
        "hypothesis": "When embedding model returns random vectors, retrieval quality "
                      "degrades gracefully and system detects the issue within 2 minutes",
        "method": "Replace embedding responses with random unit vectors "
                  "(same dimension, normalized, but semantically meaningless)",
        "blast_radius": "5% of traffic",
        "duration": "10 minutes",
        "success_criteria": [
            "Quality monitoring detects anomaly within 2 minutes",
            "System switches to keyword-based fallback retrieval",
            "No hallucinations caused by irrelevant context injection"
        ],
        "actual_results_2024_q3": {
            "detection_time": "7 minutes (FAILED — too slow)",
            "fallback_activation": "Did not activate (no detector existed!)",
            "hallucination_impact": "Quality dropped 35% — model confabulated "
                                    "when given irrelevant context",
            "action_items": [
                "Built embedding quality detector (cosine similarity sanity check)",
                "Added fallback to BM25 when embedding quality suspect",
                "Added 'context relevance gate' — LLM checks if context matches query "
                "before generating"
            ]
        }
    }

    EXPERIMENT_3 = {
        "name": "Vector DB 10x Latency",
        "hypothesis": "When vector search takes 2000ms instead of 200ms, "
                      "system applies timeout and serves degraded response within SLO",
        "method": "Inject 1800ms delay on vector DB read path via network proxy",
        "blast_radius": "10% of traffic",
        "duration": "20 minutes",
        "success_criteria": [
            "End-to-end latency stays within SLO (< 15s)",
            "System reduces top-k to minimize serial queries",
            "Cache hit rate increases as system serves cached results"
        ],
        "actual_results_2024_q3": {
            "latency_impact": "P95 went from 3s to 8s (within SLO but concerning)",
            "adaptation": "System correctly reduced top-k from 10 to 3",
            "cache_behavior": "Cache hit rate increased from 12% to 45%",
            "user_feedback": "No complaints during experiment period",
            "insight": "Users care more about getting *some* response fast than "
                       "getting the *best* response slowly"
        }
    }

    EXPERIMENT_4 = {
        "name": "Prompt Template Corruption",
        "hypothesis": "If system prompt is accidentally emptied, output monitoring "
                      "catches the behavior change within 1 minute",
        "method": "Deploy empty system prompt to 2% of traffic via feature flag",
        "blast_radius": "2% of traffic (minimum for statistical significance)",
        "duration": "5 minutes",
        "success_criteria": [
            "Output distribution anomaly detected within 1 minute",
            "Auto-rollback triggers",
            "No harmful content served (model defaults still have safety)"
        ],
        "actual_results_2024_q3": {
            "detection_time": "45 seconds (anomaly in response length distribution)",
            "auto_rollback": "Triggered successfully at 50 seconds",
            "harmful_content": "None detected (base model safety held)",
            "quality_impact": "Responses were generic but not harmful",
            "insight": "Response length is a surprisingly good canary for prompt issues"
        }
    }
```

---

## Case Study 7: On-Call Structure for AI Systems

### How NovaMind Structured AI On-Call (Different from Traditional SRE)

```yaml
on_call_structure:
  philosophy: |
    AI systems fail differently than traditional software:
    - Failures are often "soft" (quality degradation, not crashes)
    - Diagnosis requires ML knowledge (not just infrastructure skills)
    - Some issues need creative solutions (prompt engineering, not just restart)
    - Model behavior is non-deterministic (can't always reproduce issues)

  rotation:
    primary_on_call:
      role: "AI Platform Engineer"
      skills_required:
        - "Can read model metrics and identify quality regressions"
        - "Understands prompt engineering basics"
        - "Can execute runbooks for model provider issues"
        - "Familiar with vector DB operations"
      schedule: "1 week rotation, 5 engineers in pool"
      response_time: "5 minutes for SEV-1, 15 minutes for SEV-2"

    secondary_on_call:
      role: "ML Engineer (Safety/Quality Specialist)"
      skills_required:
        - "Can evaluate model output quality"
        - "Can modify prompts and safety classifiers"
        - "Can run offline evals to diagnose quality issues"
        - "Understands model internals (temperature, top-p effects)"
      schedule: "1 week rotation, 3 ML engineers in pool"
      response_time: "15 minutes for SEV-1, 30 minutes for SEV-2"
      escalation: "Primary escalates when issue is quality/safety-related"

    tertiary_on_call:
      role: "Infrastructure SRE"
      skills_required:
        - "Kubernetes, networking, GPU cluster management"
        - "Database operations (vector DB, cache)"
      schedule: "Standard infra on-call rotation"
      escalation: "When issue is clearly infrastructure (not model/quality)"

  alert_routing:
    availability_alerts: → Primary (AI Platform)
    latency_alerts: → Primary (AI Platform)
    quality_alerts: → Secondary (ML Engineer)
    safety_alerts: → Secondary (ML Engineer) + Primary simultaneously
    cost_alerts: → Primary (AI Platform)
    infrastructure_alerts: → Tertiary (Infra SRE)

  handoff_protocol:
    end_of_week: |
      Outgoing on-call writes handoff doc:
      1. Active incidents and their status
      2. Error budget status for all SLOs
      3. Any model provider changes or known issues
      4. Experiments in progress that might cause alerts
      5. Upcoming changes that might need attention

  training_program:
    for_new_on_call_engineers:
      week_1: "Shadow primary on-call"
      week_2: "Primary with experienced shadow"
      week_3: "Solo primary with fast escalation path"
    
    quarterly:
      - "Chaos engineering game day (handle simulated incidents)"
      - "Review all postmortems from past quarter"
      - "Update runbooks based on new failure modes"
```

---

## Case Study 8: Graceful Degradation Playbook

### The 4-Level Degradation Cascade

```
Level 0: HEALTHY
├── Primary model (GPT-4) serving all traffic
├── Full RAG pipeline active
├── All features enabled
└── Quality SLO: met comfortably

Level 1: PRIMARY MODEL DEGRADED (auto-triggered)
├── Trigger: Primary model latency > 3x normal OR error rate > 5%
├── Action: Route 50% traffic to secondary model (Claude 3.5)
├── User impact: Slightly different response style, ~5% quality difference
├── Duration tolerance: Up to 4 hours before human intervention
└── Auto-recovery: When primary metrics return to normal for 5 min

Level 2: ALL LIVE MODELS DEGRADED (requires human approval)
├── Trigger: Both primary and secondary models degraded
├── Action: 
│   ├── Serve from response cache for common queries (hit rate ~35%)
│   ├── Use smaller/faster model (GPT-3.5) for uncached queries
│   └── Disable features that require high-quality responses
├── User impact: Noticeable quality drop, some features unavailable
├── Communication: Status page update, in-app banner
└── Duration tolerance: Up to 2 hours

Level 3: EMERGENCY MODE (VP approval required)
├── Trigger: All model providers down OR critical safety issue
├── Action:
│   ├── Serve ONLY cached responses (no new generation)
│   ├── Queue new requests with estimated wait time
│   ├── Show "AI assistant is temporarily limited" message
│   └── Route complex queries to human support team
├── User impact: Major degradation, most AI features offline
├── Communication: Email to all users, status page, social media
└── Duration tolerance: Until resolution (no auto-recovery at this level)
```

### Real Degradation Event — March 2025

```
12:03 — OpenAI API latency spikes to 15s (normal: 1.5s)
12:04 — Circuit breaker opens for OpenAI
12:04 — AUTO: Level 1 activated. Traffic shifts to Anthropic Claude.
         User impact: None visible. Quality: 97% of normal.

12:47 — Anthropic also experiencing elevated latency (8s vs normal 2s)
12:48 — Both providers degraded. Alert fires.
12:52 — On-call engineer assesses. Neither provider is DOWN, just slow.
         Decision: Stay at Level 1 but with longer timeouts rather than Level 2.
         Rationale: Slow responses are better than cached/degraded responses.

13:15 — OpenAI recovers. Circuit breaker re-closes.
13:16 — AUTO: Traffic returns to OpenAI. Level 0 restored.
13:20 — Anthropic also recovers.

TOTAL USER IMPACT: ~45 minutes of 3x slower responses. No quality impact.
ERROR BUDGET CONSUMED: 0.3% of latency budget.
```

---

## Case Study 9: Production Monitoring Alerts (Real PagerDuty Examples)

### Alert Catalog

```yaml
alerts:
  # CRITICAL (Page immediately, wake people up)
  - name: "AI Safety Breach — Harmful Content Served"
    severity: CRITICAL
    condition: "safety_score > 0.8 detected in served response"
    pagerduty_policy: "Page primary AND secondary on-call simultaneously"
    response_sla: "Acknowledge: 5 min | Mitigate: 15 min"
    example_page: |
      🚨 [CRITICAL] AI Safety Breach Detected
      Service: writing-assistant-prod
      Time: 2025-03-14 14:23:07 UTC
      Details: Response with safety_score=0.91 served to user_id=u_7k2m9
      Content category: hate_speech (classifier confidence: 0.94)
      Action required: Investigate bypass, deploy block, assess exposure

  # HIGH (Page during business hours, alert off-hours)
  - name: "Quality SLO Error Budget < 20%"
    severity: HIGH
    condition: "quality_error_budget_remaining < 0.20"
    pagerduty_policy: "Page primary on-call (business hours) / Alert (off-hours)"
    response_sla: "Acknowledge: 15 min | Investigation: 1 hour"
    example_page: |
      ⚠️ [HIGH] Quality Error Budget Critical
      Service: customer-support-ai
      SLO: helpfulness_92pct (30d rolling)
      Budget remaining: 18% (was 35% yesterday)
      Burn rate: 4.2x normal
      Trend: Will exhaust in ~3 days at current rate
      Recent changes: New prompt template deployed 6h ago (correlates)

  # MEDIUM (Alert, respond within 1 hour during business hours)
  - name: "Model Provider Latency Elevated"
    severity: MEDIUM
    condition: "provider_latency_p95 > 2x baseline for 10 minutes"
    response_sla: "Acknowledge: 30 min | Assess: 1 hour"
    example_page: |
      📊 [MEDIUM] Provider Latency Elevated
      Provider: OpenAI (gpt-4-turbo)
      Current P95: 4.2s (baseline: 1.8s)
      Duration: 12 minutes
      Impact: End-to-end latency SLO at risk (P95 now 6.8s, target 8s)
      Auto-mitigation: Circuit breaker at 50% threshold (not yet triggered)

  # LOW (Ticket, address next business day)  
  - name: "AI Cost Anomaly"
    severity: LOW
    condition: "hourly_cost > 1.5x 7d_average_same_hour"
    response_sla: "Review next business day"
    example_page: |
      💰 [LOW] Cost Anomaly Detected
      Service: document-analysis
      Current hourly spend: $847 (7d avg for this hour: $520)
      Delta: +63%
      Likely cause: New customer onboarded 2 days ago (100K docs imported)
      Action: Verify expected, update cost forecast

  - name: "Embedding Index Staleness"
    severity: LOW
    condition: "newest_document_in_index > 24 hours old AND new_docs_pending > 100"
    response_sla: "Review next business day"
    example_page: |
      📋 [LOW] Embedding Index Stale
      Collection: enterprise-knowledge-base
      Last indexed: 28 hours ago
      Documents pending: 342
      Cause: Indexing pipeline job failed (OOM on large batch)
      Impact: Users won't find content added in last 28 hours
```

---

## Case Study 10: Post-Incident Review — Silent Embedding Model Quality Drop

### Blameless Postmortem: "The Invisible Regression"

```
═══════════════════════════════════════════════════════════════════
         BLAMELESS POSTMORTEM — INC-2025-0312
         "Silent Embedding Model Quality Drop"
═══════════════════════════════════════════════════════════════════

INCIDENT SUMMARY
────────────────
Date: February 12-19, 2025 (7 days undetected)
Severity: SEV-2
Impact: ~15% quality degradation for enterprise search feature
Users affected: ~45,000 (all enterprise tier users)
Error budget consumed: 62% of monthly quality budget in 7 days
Revenue impact: 3 enterprise customers escalated support tickets;
                1 customer initiated contract review discussion

ROOT CAUSE
──────────
On Feb 12, our embedding model provider (Cohere) silently updated
their embed-english-v3.0 endpoint. The update was a minor patch
(v3.0.1 → v3.0.2) that:

- Changed embedding space geometry slightly
- Existing vectors and new vectors were no longer perfectly aligned
- Cosine similarity between old and new embeddings of SAME text: 0.92
  (should be ~0.99+ for same-model embeddings)

This meant:
- New queries embedded with v3.0.2
- Existing knowledge base vectors were v3.0.1
- Retrieval recall dropped from 0.91 to 0.78
- RAG responses became less grounded (wrong documents retrieved)

WHY IT TOOK 7 DAYS TO DETECT
─────────────────────────────
1. Quality monitoring uses LLM-judge on 10% sample → statistical noise
   masked the signal for first 3 days
2. Quality degradation was gradual (not all queries affected equally)
3. Users didn't immediately report — they thought THEY were asking
   wrong questions
4. Embedding model version was not monitored (no fingerprinting)
5. Provider did not notify customers of the update

TIMELINE
────────
Feb 12 08:00 — Cohere deploys embed-english-v3.0.2 (we don't know)
Feb 12-14    — Quality score: 89% → 86% (within noise band, no alert)
Feb 15       — Quality score: 84% (still within SLO of 85%, no alert)
Feb 16       — Quality score: 82% (SLO BREACHED — alert fires)
               On-call investigates. Sees quality drop but can't identify cause.
               Hypothesis: "Maybe users are asking harder questions this week"
               Action: Monitoring increased, no mitigation.
Feb 17       — Quality score: 80%. Escalated to ML team.
Feb 18       — ML team runs diagnostic:
               - Generation quality (isolated): Normal ✓
               - Retrieval recall: 0.78 (should be 0.91) ✗ ← Found it
               - Embedding sanity check: cosine sim of re-embedded docs: 0.92 ✗
               Root cause identified: embedding model version change
Feb 19 09:00 — FIX: Full reindex of knowledge base with current model version
Feb 19 14:00 — Reindex complete. Quality back to 89%.

WHAT WENT WELL
──────────────
- Once ML team investigated, root cause found within hours
- Reindexing infrastructure handled full reindex without downtime
- No harmful content produced (just less relevant responses)
- Customer success team proactively reached out to affected customers

WHAT WENT POORLY
────────────────
- 7 days to detection is unacceptable for a quality regression
- On-call engineer dismissed the signal on Day 4 without deeper investigation
- No embedding model version monitoring existed
- Provider gives no notification of minor updates
- Quality SLO alerting was too slow (needed multi-day trend to fire)

ACTION ITEMS
────────────
| # | Action | Owner | Priority | Due |
|---|--------|-------|----------|-----|
| 1 | Build embedding fingerprint monitor (daily re-embed 100 reference texts, alert if cosine sim < 0.98) | ML Platform | P0 | Feb 26 |
| 2 | Add "retrieval recall" as separate SLO (not just end-to-end quality) | SRE Team | P0 | Mar 1 |
| 3 | Pin embedding model version where possible (use versioned endpoints) | ML Platform | P1 | Mar 5 |
| 4 | Reduce quality alert detection window from 48h to 6h (accept more false positives) | SRE Team | P1 | Feb 28 |
| 5 | Automated reindex trigger when embedding drift detected | Data Platform | P2 | Mar 15 |
| 6 | Establish communication channel with Cohere for change notifications | Vendor Mgmt | P1 | Mar 1 |
| 7 | Update on-call training: "quality drop = investigate, never dismiss" | SRE Lead | P1 | Mar 5 |

LESSONS FOR THE INDUSTRY
─────────────────────────
1. Embedding model versions are a hidden dependency that most teams don't monitor.
2. "Silent updates" from model providers are the AI equivalent of a dependency
   vulnerability — you need version pinning and drift detection.
3. Quality SLOs need FAST detection (hours, not days) even if it means more
   false positives.
4. Retrieval quality should be monitored SEPARATELY from generation quality.
   If you only monitor the end-to-end output, you can't localize regressions.
5. The "it's probably just noise" instinct kills you with AI systems.
   AI metrics are noisy by nature — you need better statistical methods,
   not higher thresholds.

═══════════════════════════════════════════════════════════════════
```

---

## Summary: Key Differences Between Traditional SRE and AI SRE

| Dimension | Traditional SRE | AI SRE |
|-----------|----------------|--------|
| Failure mode | Binary (works/broken) | Gradient (quality spectrum) |
| Detection | Error rates, latency | Quality scores, drift detection |
| Root cause | Code bug, infra failure | Model change, data drift, prompt issue |
| Mitigation | Rollback, restart | Model swap, prompt fix, reindex |
| On-call skills | Infra, networking | ML, NLP, prompt engineering |
| SLOs | Availability, latency | + Quality, groundedness, safety |
| Chaos testing | Kill services, network partition | Corrupt embeddings, degrade models |
| Postmortems | "Server crashed because..." | "Quality dropped because embedding space shifted..." |
