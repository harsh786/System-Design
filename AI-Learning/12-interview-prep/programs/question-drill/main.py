#!/usr/bin/env python3
"""
AI Architect Interview Question Drill
Draws random questions from a bank of 50+ across multiple categories,
shows key points, differentiators, common mistakes, and follow-ups.
"""

import random
import time

# ============================================================================
# QUESTION BANK (50+ questions across 7 categories)
# ============================================================================

QUESTIONS = {
    "RAG": [
        {
            "q": "How would you handle a RAG system where the retrieved documents are contradictory?",
            "key_points": [
                "Acknowledge contradiction explicitly in the response",
                "Use metadata (date, authority, specificity) to rank conflicting sources",
                "Present multiple perspectives with citations",
                "Let the user decide when genuinely ambiguous",
            ],
            "differentiators": [
                "Design a conflict detection module that flags contradictions before generation",
                "Implement source authority hierarchy (regulation > policy > FAQ)",
                "Show how this connects to trust calibration in the UI",
            ],
            "mistakes": [
                "Ignoring the contradiction and picking arbitrarily",
                "Saying 'just use a better model'",
                "Not considering that contradictions might indicate stale data",
            ],
            "followups": [
                "How would you detect contradictions programmatically?",
                "What if the contradiction is between a recent document and an older authoritative one?",
                "How does this change your chunking strategy?",
            ],
        },
        {
            "q": "Your RAG system has high retrieval recall but low answer quality. Diagnose.",
            "key_points": [
                "Problem is likely in the generation phase, not retrieval",
                "Check: are retrieved chunks actually relevant (recall != precision)?",
                "Check: is the context too long / noisy for the LLM?",
                "Check: is the LLM following instructions to use the context?",
            ],
            "differentiators": [
                "Build a diagnostic pipeline: retrieval quality -> context quality -> generation quality",
                "Implement a re-ranking step between retrieval and generation",
                "Analyze failure modes: hallucination vs. ignoring context vs. wrong context selection",
            ],
            "mistakes": [
                "Immediately suggesting a bigger/better model",
                "Conflating retrieval metrics with end-to-end quality",
                "Not considering the context window management problem",
            ],
            "followups": [
                "How would you set up an evaluation pipeline for this?",
                "What metrics would you track at each stage?",
                "When would you invest in fine-tuning vs. better retrieval?",
            ],
        },
        {
            "q": "How do you evaluate a RAG system end-to-end?",
            "key_points": [
                "Separate retrieval metrics (recall@k, MRR) from generation metrics",
                "Faithfulness: does the answer match the retrieved context?",
                "Relevance: does the answer address the user's question?",
                "Human evaluation for nuanced quality assessment",
            ],
            "differentiators": [
                "LLM-as-judge for scalable evaluation with human calibration",
                "Build regression test suites from production failures",
                "Track metrics per query type (factual vs. reasoning vs. summarization)",
            ],
            "mistakes": [
                "Only measuring BLEU/ROUGE (surface-level similarity)",
                "No evaluation of retrieval independent of generation",
                "Not having a golden dataset for regression testing",
            ],
            "followups": [
                "How do you handle evaluating open-ended questions?",
                "What's your CI/CD pipeline for RAG quality?",
                "How do you detect quality degradation in production?",
            ],
        },
        {
            "q": "Design a chunking strategy for technical documentation with code examples.",
            "key_points": [
                "Preserve code blocks as atomic units (never split mid-code)",
                "Include surrounding explanatory text with code chunks",
                "Hierarchical chunking: page -> section -> paragraph/code block",
                "Metadata: language, function names, imports for better retrieval",
            ],
            "differentiators": [
                "AST-aware chunking for code (function-level, class-level)",
                "Cross-reference preservation (when text references code and vice versa)",
                "Multi-representation: store both the code and a natural language summary",
            ],
            "mistakes": [
                "Fixed-size chunking that splits code blocks",
                "Not indexing code separately from prose",
                "Ignoring the relationship between explanatory text and code",
            ],
            "followups": [
                "How would this change for API reference docs vs. tutorials?",
                "How do you handle versioned documentation?",
                "What embedding model works best for mixed code/text?",
            ],
        },
        {
            "q": "How would you implement multi-hop reasoning in a RAG system?",
            "key_points": [
                "Iterative retrieval: first query -> retrieve -> extract entities -> second query",
                "Query decomposition: break complex question into sub-questions",
                "Graph-based retrieval for following relationships between documents",
                "Chain-of-thought prompting to guide multi-step reasoning",
            ],
            "differentiators": [
                "Implement a query planner that decides retrieval strategy based on question type",
                "Build a knowledge graph overlay on top of vector retrieval",
                "Show awareness of cost/latency tradeoffs of multiple retrieval rounds",
            ],
            "mistakes": [
                "Assuming single-shot retrieval handles all query types",
                "Not setting a maximum hop limit (infinite loops)",
                "Ignoring the compounding error problem in multi-hop",
            ],
            "followups": [
                "How do you know when to stop retrieving?",
                "What's the latency impact and how do you mitigate it?",
                "How do you evaluate multi-hop accuracy separately?",
            ],
        },
        {
            "q": "Your RAG system works in English but fails in Japanese. Why and how to fix?",
            "key_points": [
                "Embedding models may not be multilingual or equally good across languages",
                "Tokenization differs (no spaces in Japanese = different chunking)",
                "Retrieval scoring may be biased toward English",
                "Cross-lingual retrieval if docs are in one language and queries in another",
            ],
            "differentiators": [
                "Use multilingual embedding models (e.g., multilingual-e5)",
                "Language-specific chunking strategies (morphological analysis for Japanese)",
                "Separate evaluation datasets per language to track quality independently",
            ],
            "mistakes": [
                "Assuming one embedding model works equally well for all languages",
                "Not testing with native speakers",
                "Translating everything to English as a hack",
            ],
            "followups": [
                "How would you handle a query in Japanese about an English document?",
                "What about low-resource languages?",
                "How does this affect your evaluation strategy?",
            ],
        },
        {
            "q": "How do you handle document updates in a production RAG system?",
            "key_points": [
                "Incremental indexing (don't re-embed everything)",
                "Version tracking: which chunks are current vs. superseded",
                "Cache invalidation for any cached query results",
                "Handle partial updates (one section of a document changed)",
            ],
            "differentiators": [
                "Change detection pipeline with diff-based re-chunking",
                "Temporal relevance scoring (prefer current versions)",
                "Audit trail: which answers were served with now-outdated context",
            ],
            "mistakes": [
                "Full re-index on every change (doesn't scale)",
                "No versioning (serving stale content without knowing)",
                "Not considering the impact on cached/memoized results",
            ],
            "followups": [
                "What if a critical correction is made? How fast must it propagate?",
                "How do you handle conflicting versions during transition?",
                "What's your rollback strategy if a bad update goes live?",
            ],
        },
    ],
    "Agents": [
        {
            "q": "How do you prevent an AI agent from taking irreversible harmful actions?",
            "key_points": [
                "Action classification: reversible vs. irreversible",
                "Approval gates for high-risk actions",
                "Sandboxing: dry-run mode for testing action sequences",
                "Budget limits (financial, API calls, resource creation)",
            ],
            "differentiators": [
                "Design a graduated trust system (earn more autonomy over time)",
                "Implement action impact prediction before execution",
                "Build undo/compensation mechanisms for semi-reversible actions",
            ],
            "mistakes": [
                "Relying solely on prompt engineering for safety",
                "No distinction between action severity levels",
                "Not considering multi-step attack sequences",
            ],
            "followups": [
                "How do you handle time-sensitive actions that can't wait for approval?",
                "What's your monitoring strategy for agent behavior drift?",
                "How do you test agent safety without risking production?",
            ],
        },
        {
            "q": "Design an agent orchestration system for a complex multi-step workflow.",
            "key_points": [
                "DAG-based workflow definition with conditional branching",
                "State management: persist intermediate results",
                "Error handling: retry, fallback, human escalation",
                "Observability: trace each step, measure latency and cost",
            ],
            "differentiators": [
                "Dynamic replanning when steps fail or conditions change",
                "Resource-aware scheduling (don't overwhelm APIs)",
                "Checkpoint and resume for long-running workflows",
            ],
            "mistakes": [
                "Linear chain-only thinking (no parallelism or branching)",
                "No state persistence (one failure restarts everything)",
                "Ignoring cost accumulation across steps",
            ],
            "followups": [
                "How do you handle a step that's taking 10x longer than expected?",
                "What's your testing strategy for multi-agent workflows?",
                "How do you version and deploy workflow changes safely?",
            ],
        },
        {
            "q": "How do you evaluate agent performance beyond task completion?",
            "key_points": [
                "Efficiency: steps taken vs. minimum needed",
                "Cost: tokens/API calls consumed per task",
                "Safety: did it violate any constraints?",
                "User experience: was the interaction smooth?",
            ],
            "differentiators": [
                "Build benchmarks that test edge cases and adversarial inputs",
                "Measure 'regret' - how often does the agent take suboptimal paths",
                "Compare against human expert baselines for complex tasks",
            ],
            "mistakes": [
                "Only measuring success/failure binary",
                "Not tracking cost per successful task",
                "Ignoring partial success (90% correct but missed one step)",
            ],
            "followups": [
                "How do you detect agent performance degradation over time?",
                "What's your A/B testing strategy for agent improvements?",
                "How do you handle tasks with no clear 'correct' answer?",
            ],
        },
    ],
    "Infrastructure": [
        {
            "q": "How would you design an LLM serving infrastructure for 99.9% uptime?",
            "key_points": [
                "Multi-provider failover (OpenAI -> Anthropic -> self-hosted)",
                "Health checks and circuit breakers",
                "Request queuing with timeout and retry",
                "Graceful degradation (serve cached/simpler responses when degraded)",
            ],
            "differentiators": [
                "Prompt adaptation layer (different models need different prompts)",
                "Capacity planning with token-based (not request-based) quotas",
                "Chaos engineering: regularly test failover paths",
            ],
            "mistakes": [
                "Single provider dependency",
                "Not accounting for rate limits as a failure mode",
                "Treating all requests equally (no priority system)",
            ],
            "followups": [
                "How do you handle a scenario where all providers are degraded?",
                "What's your capacity planning process?",
                "How do you test failover without affecting production?",
            ],
        },
        {
            "q": "Design a feature store for ML/AI features that serves both batch and real-time.",
            "key_points": [
                "Dual-write architecture: batch features computed offline, real-time features computed on events",
                "Point-in-time correctness for training (avoid data leakage)",
                "Low-latency serving layer (Redis/DynamoDB) for online inference",
                "Feature versioning and lineage tracking",
            ],
            "differentiators": [
                "Unified feature definition that works for both batch and streaming",
                "Feature quality monitoring (drift detection, missing values)",
                "Self-service feature creation with governance guardrails",
            ],
            "mistakes": [
                "Training-serving skew (different code paths for same feature)",
                "No point-in-time correctness (using future data in training)",
                "Not considering feature freshness requirements per use case",
            ],
            "followups": [
                "How do you handle feature dependencies?",
                "What's your strategy for feature deprecation?",
                "How do you debug a production issue caused by a bad feature?",
            ],
        },
        {
            "q": "How do you manage GPU resources efficiently for AI workloads?",
            "key_points": [
                "Separate training (batch, can be preempted) from inference (latency-sensitive)",
                "Auto-scaling based on queue depth, not just CPU/memory",
                "GPU sharing/fractional allocation for small models",
                "Spot/preemptible instances for training with checkpointing",
            ],
            "differentiators": [
                "Multi-tenant GPU scheduling with priority and fairness",
                "Cost attribution per team/project for chargebacks",
                "Predictive scaling based on traffic patterns (not just reactive)",
            ],
            "mistakes": [
                "Treating GPU like CPU (same scaling strategies don't apply)",
                "No separation between training and inference clusters",
                "Over-provisioning because scaling is too slow",
            ],
            "followups": [
                "How do you handle GPU memory fragmentation?",
                "What's your strategy for GPU upgrades (A100 -> H100 migration)?",
                "How do you prioritize when demand exceeds capacity?",
            ],
        },
    ],
    "Security": [
        {
            "q": "How do you defend against prompt injection in a production AI system?",
            "key_points": [
                "Input sanitization and classification (is this an attack?)",
                "Privilege separation: LLM cannot directly call high-risk tools",
                "Output validation: check responses for data leakage",
                "Principle of least privilege for all tool access",
            ],
            "differentiators": [
                "Defense in depth: multiple independent detection layers",
                "Red team regularly with evolving attack techniques",
                "Behavioral anomaly detection (unusual action patterns)",
            ],
            "mistakes": [
                "Relying on a single 'ignore previous instructions' filter",
                "Assuming the model will follow system prompt instructions",
                "Not testing with sophisticated multi-turn attacks",
            ],
            "followups": [
                "What about indirect prompt injection via retrieved documents?",
                "How do you balance security with user experience?",
                "How do you stay current with new attack vectors?",
            ],
        },
        {
            "q": "Design a data privacy architecture for an AI system handling PII.",
            "key_points": [
                "PII detection and classification at ingestion",
                "Data minimization: only store what's needed",
                "Encryption at rest and in transit, tokenization for sensitive fields",
                "Access controls and audit logging",
            ],
            "differentiators": [
                "Privacy-preserving AI techniques (federated learning, differential privacy)",
                "Data lifecycle management (automatic deletion per retention policy)",
                "Cross-border data handling with jurisdiction-aware routing",
            ],
            "mistakes": [
                "Sending raw PII to third-party LLM APIs",
                "No data retention policy (storing everything forever)",
                "Logging prompts/responses containing PII without redaction",
            ],
            "followups": [
                "How do you handle PII that's embedded in unstructured text?",
                "What's your approach to GDPR right-to-erasure with vector databases?",
                "How do you audit what data the AI system has accessed?",
            ],
        },
        {
            "q": "How do you secure a multi-tenant AI platform?",
            "key_points": [
                "Strict tenant isolation (data, models, API keys)",
                "Prevent cross-tenant data leakage in shared models",
                "Per-tenant encryption keys",
                "Network segmentation and access controls",
            ],
            "differentiators": [
                "Formal isolation verification (prove no data leakage path exists)",
                "Tenant-specific model fine-tuning without cross-contamination",
                "Zero-trust architecture within the platform",
            ],
            "mistakes": [
                "Shared vector database without tenant filtering",
                "Using same API keys across tenants",
                "Not considering side-channel attacks (timing, cache)",
            ],
            "followups": [
                "How do you handle a tenant requesting their data be deleted?",
                "What about shared base models that all tenants use?",
                "How do you detect a breach in a multi-tenant system?",
            ],
        },
    ],
    "Scaling": [
        {
            "q": "Your LLM application handles 100 req/s. Design it for 10,000 req/s.",
            "key_points": [
                "Identify the bottleneck: is it compute, memory, network, or API rate limits?",
                "Semantic caching for repeated/similar queries",
                "Batch inference where possible",
                "Horizontal scaling with load balancing",
            ],
            "differentiators": [
                "Request classification: route simple queries to fast/cheap path",
                "Speculative execution: start generating while still retrieving",
                "Capacity planning model: tokens/second budget across the fleet",
            ],
            "mistakes": [
                "Assuming linear scaling (10x instances = 10x throughput)",
                "Ignoring the cost implications of 100x scale",
                "Not considering tail latency at high percentiles",
            ],
            "followups": [
                "What's your approach to handling traffic spikes (10x normal)?",
                "How does cost change at this scale? What optimizations matter?",
                "What breaks first when you hit capacity?",
            ],
        },
        {
            "q": "How do you handle embedding 1 billion documents?",
            "key_points": [
                "Batch processing with distributed compute",
                "Incremental embedding (don't re-embed unchanged docs)",
                "Sharded vector index across multiple nodes",
                "Approximate nearest neighbor (ANN) with acceptable recall trade-off",
            ],
            "differentiators": [
                "Tiered indexing: hot data in memory, warm on SSD, cold in object storage",
                "Index build strategy: offline build -> swap (no downtime)",
                "Embedding model selection based on dimension vs quality vs cost curve",
            ],
            "mistakes": [
                "Trying to fit everything in one vector DB instance",
                "Not planning for index rebuild when changing embedding models",
                "Ignoring the time cost (1B docs x 0.1s = 3 years on 1 machine)",
            ],
            "followups": [
                "How long does the initial embedding take? How do you parallelize?",
                "What's your strategy when you want to change embedding models?",
                "How do you handle queries that span multiple shards?",
            ],
        },
        {
            "q": "Design a system that can serve 50 different ML models with varying latency requirements.",
            "key_points": [
                "Model registry with SLA metadata (latency, throughput requirements)",
                "Heterogeneous serving: different hardware for different model types",
                "Shared inference infrastructure with isolation",
                "Auto-scaling per model based on traffic patterns",
            ],
            "differentiators": [
                "Model placement optimization (bin-packing on GPU memory)",
                "Traffic-aware scheduling (batch low-priority, prioritize latency-sensitive)",
                "Canary deployments per model with automated rollback",
            ],
            "mistakes": [
                "One-size-fits-all serving infrastructure",
                "Not accounting for model loading time (cold start)",
                "Ignoring GPU memory fragmentation with many models",
            ],
            "followups": [
                "How do you handle a model that suddenly gets 10x traffic?",
                "What's your model update strategy (zero-downtime)?",
                "How do you monitor quality across 50 models efficiently?",
            ],
        },
    ],
    "Cost": [
        {
            "q": "Your AI feature costs $2M/month. The CEO wants it under $500K. What do you do?",
            "key_points": [
                "First: understand the cost breakdown (which components cost what)",
                "Caching: avoid redundant LLM calls for similar queries",
                "Model tiering: use cheaper models for simple queries",
                "Batch processing where real-time isn't needed",
            ],
            "differentiators": [
                "Build a cost attribution system (cost per feature, per user segment)",
                "ROI analysis: which AI features actually drive revenue?",
                "Progressive optimization: quick wins first, architectural changes second",
            ],
            "mistakes": [
                "Immediately suggesting to switch to open-source (may not be quality-equivalent)",
                "Cutting quality without measuring business impact",
                "Not considering the cost of optimization work itself",
            ],
            "followups": [
                "How do you maintain quality while cutting costs?",
                "What's your monitoring strategy to catch cost regressions?",
                "How do you make the case to leadership for the timeline needed?",
            ],
        },
        {
            "q": "How do you build a cost-aware AI architecture from day one?",
            "key_points": [
                "Token metering at every LLM call",
                "Budget alerts and automatic throttling",
                "Cost per request tracking (not just monthly bills)",
                "Design for cacheability from the start",
            ],
            "differentiators": [
                "Economic model: understand unit economics of AI features",
                "Cost feedback loops: show developers the cost of their prompts",
                "Architecture that allows easy model swapping for cost optimization",
            ],
            "mistakes": [
                "Treating AI costs as a fixed infrastructure expense",
                "No per-feature or per-team cost attribution",
                "Optimizing prematurely before understanding value",
            ],
            "followups": [
                "How do you handle cost spikes from adversarial users?",
                "What's your strategy for budgeting AI costs in a growing product?",
                "How do you balance cost control with developer velocity?",
            ],
        },
        {
            "q": "Compare the TCO of self-hosted open-source LLMs vs. API providers.",
            "key_points": [
                "API: variable cost per token, zero infrastructure, rate limited",
                "Self-hosted: high fixed cost (GPUs), low marginal cost, full control",
                "Breakeven analysis based on volume",
                "Hidden costs: MLOps team, hardware refresh, model updates",
            ],
            "differentiators": [
                "Include opportunity cost (what else could the team be building?)",
                "Consider data privacy as a non-cost factor that may force self-hosting",
                "Hybrid approach: self-host for high-volume, API for spiky/specialized",
            ],
            "mistakes": [
                "Only comparing per-token cost (ignoring ops overhead)",
                "Not considering model quality differences",
                "Ignoring the speed-to-market advantage of APIs",
            ],
            "followups": [
                "At what volume does self-hosting break even?",
                "How do you handle model updates with self-hosted?",
                "What's your staffing plan for managing self-hosted infrastructure?",
            ],
        },
    ],
    "Evaluation": [
        {
            "q": "How do you detect model quality degradation in production?",
            "key_points": [
                "Automated quality metrics on a sample of production traffic",
                "User feedback signals (thumbs up/down, regenerate clicks, abandonment)",
                "Drift detection on input distributions",
                "Regression test suite run on every model/prompt change",
            ],
            "differentiators": [
                "Statistical process control (detect shifts vs. normal variation)",
                "Segment-level monitoring (degradation may only affect certain query types)",
                "Automated root cause analysis (is it the model, data, or infrastructure?)",
            ],
            "mistakes": [
                "Only checking average metrics (hides segment-level issues)",
                "No baseline or historical comparison",
                "Alert fatigue from noisy metrics with no actionable threshold",
            ],
            "followups": [
                "How do you distinguish model degradation from changing user behavior?",
                "What's your response playbook when quality drops?",
                "How do you handle quality issues from upstream API providers?",
            ],
        },
        {
            "q": "Design an evaluation framework for an AI coding assistant.",
            "key_points": [
                "Functional correctness (does the code run and pass tests?)",
                "Code quality (style, efficiency, maintainability)",
                "Relevance (does it solve the user's actual problem?)",
                "Safety (does it introduce vulnerabilities?)",
            ],
            "differentiators": [
                "Multi-turn evaluation (does context from conversation improve suggestions?)",
                "Task-complexity stratification (simple completions vs. architectural suggestions)",
                "Comparison with human expert baselines on the same tasks",
            ],
            "mistakes": [
                "Only measuring acceptance rate (users accept mediocre code too)",
                "Not testing adversarial inputs (trick the AI into insecure code)",
                "Ignoring downstream effects (does AI code cause more bugs later?)",
            ],
            "followups": [
                "How do you evaluate subjective code quality?",
                "What benchmarks would you create vs. use off-the-shelf?",
                "How do you measure productivity impact (not just code quality)?",
            ],
        },
        {
            "q": "How do you evaluate hallucination rates in a generative AI system?",
            "key_points": [
                "Define hallucination types: factual errors, unsupported claims, fabricated sources",
                "Automated checking against ground truth where available",
                "LLM-as-judge for detecting unsupported claims",
                "Human evaluation sample for calibration",
            ],
            "differentiators": [
                "Distinguish intrinsic hallucination (contradicts source) vs. extrinsic (adds info not in source)",
                "Context-dependent severity scoring (medical > entertainment)",
                "Production monitoring with automated hallucination detection pipeline",
            ],
            "mistakes": [
                "Binary classification (hallucination or not) without severity",
                "Only testing on easy/factual questions",
                "Not measuring hallucination rate per topic/domain",
            ],
            "followups": [
                "How does hallucination rate change with longer contexts?",
                "What's an acceptable hallucination rate for your use case?",
                "How do you handle cases where ground truth is unavailable?",
            ],
        },
    ],
}

# ============================================================================
# DRILL ENGINE
# ============================================================================

def print_header(text, char="="):
    width = 78
    print(f"\n{char * width}")
    print(f" {text}")
    print(f"{char * width}")


def print_section(title, items, indent=4):
    print(f"\n  {title}:")
    for item in items:
        print(f"{' ' * indent}- {item}")


def run_drill():
    print_header("AI ARCHITECT INTERVIEW QUESTION DRILL")
    print("""
    This drill presents random questions from a bank of 50+ across 7 categories.
    For each question, you'll see:
      - Key points (minimum viable answer)
      - Differentiators (what makes a Staff answer stand out)
      - Common mistakes to avoid
      - Follow-up questions to prepare for

    Categories: RAG, Agents, Infrastructure, Security, Scaling, Cost, Evaluation
    """)

    # Select questions - one from each category plus extras
    all_questions = []
    for category, questions in QUESTIONS.items():
        for q in questions:
            all_questions.append((category, q))

    # Randomly select 10 questions ensuring category diversity
    categories = list(QUESTIONS.keys())
    selected = []
    # One from each category first
    for cat in categories:
        q = random.choice(QUESTIONS[cat])
        selected.append((cat, q))
    # Then 3 more random ones
    remaining = [(c, q) for c, q in all_questions if (c, q) not in selected]
    selected.extend(random.sample(remaining, min(3, len(remaining))))
    random.shuffle(selected)

    # Track scores
    scores = {cat: {"asked": 0, "max_points": 0} for cat in categories}
    total_questions = len(selected)

    for i, (category, question) in enumerate(selected, 1):
        print_header(f"QUESTION {i}/{total_questions} [{category.upper()}]", "-")
        print(f"\n  Q: {question['q']}\n")
        time.sleep(0.5)

        # Self-assessment prompt
        print("  ┌─────────────────────────────────────────────────────────────┐")
        print("  │ Think about your answer before reading below...             │")
        print("  │ Would you cover all key points? Any differentiators?        │")
        print("  └─────────────────────────────────────────────────────────────┘")
        time.sleep(0.5)

        print_section("KEY POINTS (must cover for a passing answer)", question["key_points"])
        print_section("DIFFERENTIATORS (Staff-level insights)", question["differentiators"])
        print_section("COMMON MISTAKES (avoid these)", question["mistakes"])
        print_section("LIKELY FOLLOW-UPS (prepare for these)", question["followups"])

        # Scoring guide
        print(f"\n  SELF-SCORE:")
        print(f"    0 - Couldn't answer or made a common mistake")
        print(f"    1 - Covered some key points")
        print(f"    2 - Covered all key points")
        print(f"    3 - Key points + differentiators")

        scores[category]["asked"] += 1
        scores[category]["max_points"] += 3

    # Summary
    print_header("DRILL SUMMARY")
    print(f"\n  Questions completed: {total_questions}")
    print(f"\n  Category Coverage:")
    print(f"  {'Category':<16} {'Questions':>10} {'Notes':<40}")
    print(f"  {'─' * 66}")

    weak_areas = []
    for cat in categories:
        asked = scores[cat]["asked"]
        if asked > 0:
            note = "Covered" if asked >= 2 else "Need more practice"
            if asked < 2:
                weak_areas.append(cat)
            print(f"  {cat:<16} {asked:>10} {note:<40}")
        else:
            weak_areas.append(cat)
            print(f"  {cat:<16} {'0':>10} {'NOT TESTED - review these!':<40}")

    if weak_areas:
        print(f"\n  AREAS TO FOCUS ON: {', '.join(weak_areas)}")
        print(f"  Run the drill again for more questions in these categories.")

    print(f"\n  PREPARATION TIPS:")
    print(f"    1. For each question, practice answering aloud in 2-3 minutes")
    print(f"    2. Always start with the key points, then add differentiators")
    print(f"    3. If you catch yourself making a 'common mistake', reframe")
    print(f"    4. Prepare for follow-ups - they test depth vs. memorization")
    print(f"    5. Staff answers connect technical details to business impact")

    print(f"\n  Total questions in bank: {sum(len(qs) for qs in QUESTIONS.values())}")
    print(f"  Run again for different questions!\n")


if __name__ == "__main__":
    run_drill()
