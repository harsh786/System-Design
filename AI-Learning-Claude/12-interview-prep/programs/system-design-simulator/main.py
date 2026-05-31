#!/usr/bin/env python3
"""
System Design Interview Simulator for AI Architects
Presents realistic AI system design problems and walks through
the expected interview structure with good vs mediocre answers.
"""

import random
import time
import textwrap

# ============================================================================
# SCENARIOS
# ============================================================================

SCENARIOS = [
    {
        "title": "Design a RAG system for 10M legal documents",
        "context": "A law firm wants to build an AI assistant that can answer questions "
                   "about their 10 million legal documents (cases, contracts, regulations). "
                   "Lawyers need accurate, citation-backed answers in under 5 seconds.",
        "requirements": {
            "good_questions": [
                "What's the average document length? (Important for chunking strategy)",
                "What types of queries - factual lookup vs. legal reasoning vs. summarization?",
                "What accuracy/hallucination tolerance? (Legal = near zero tolerance)",
                "Do we need multi-document reasoning (cross-reference cases)?",
                "What's the update frequency? New documents daily or batch monthly?",
                "Who are the users - paralegals, junior lawyers, senior partners?",
                "Any compliance requirements - data residency, audit trails?",
                "What's the latency budget breakdown - retrieval vs generation?",
            ],
            "mediocre_questions": [
                "How many users?",
                "What cloud provider?",
                "What's the budget?",
            ],
            "why": "Good questions reveal constraints that drive architecture. Mediocre "
                   "questions are generic and don't inform design decisions.",
        },
        "architecture": {
            "good": {
                "components": [
                    "Document Ingestion Pipeline: PDF parsing -> chunking (hierarchical, "
                    "500-token chunks with 100-token overlap, preserving section headers) "
                    "-> embedding (domain-fine-tuned model) -> vector store",
                    "Hybrid Retrieval: Dense retrieval (vector similarity) + Sparse retrieval "
                    "(BM25 on legal terms) + Metadata filtering (jurisdiction, date, type)",
                    "Re-ranking Layer: Cross-encoder re-ranker trained on legal relevance, "
                    "plus citation verification step",
                    "Generation with Guardrails: LLM with system prompt enforcing citations, "
                    "output validator checking all claims have source references",
                    "Feedback Loop: Lawyer ratings -> fine-tune retrieval and re-ranking",
                ],
                "diagram": textwrap.dedent("""
                    User Query
                        |
                    [Query Understanding] -- intent classification, entity extraction
                        |
                    [Hybrid Retrieval]
                    /        |        \\
                [Vector]  [BM25]  [Metadata Filter]
                    \\       |        /
                    [Re-ranker + Dedup]
                        |
                    [Context Assembly] -- hierarchical, with surrounding sections
                        |
                    [LLM Generation] -- with citation enforcement
                        |
                    [Output Validator] -- hallucination check, citation verify
                        |
                    Response with Citations
                """),
            },
            "mediocre": {
                "components": [
                    "Put documents in a vector database",
                    "Use embeddings to find similar documents",
                    "Send to GPT-4 with the context",
                    "Return the answer",
                ],
                "why": "Missing: chunking strategy, hybrid retrieval, re-ranking, "
                       "guardrails, feedback loops. This is a tutorial-level answer.",
            },
        },
        "deep_dives": [
            {
                "topic": "Chunking Strategy",
                "good": "Hierarchical chunking: document -> sections -> paragraphs. "
                        "Each chunk carries metadata (doc_id, section_path, page_num). "
                        "Use recursive splitting respecting legal document structure "
                        "(clauses, sub-clauses). Overlap of 100 tokens to preserve context "
                        "at boundaries. Store parent-child relationships for context expansion.",
                "mediocre": "Split documents into 500-token chunks.",
                "why": "Legal documents have deep structure. Naive splitting loses context "
                       "and breaks cross-references between clauses.",
            },
            {
                "topic": "Handling Hallucinations in Legal Context",
                "good": "Multi-layer approach: (1) Constrained generation - LLM must quote "
                        "verbatim from retrieved chunks, (2) Citation verification - post-hoc "
                        "check that each claim maps to a source, (3) Confidence scoring - "
                        "flag low-confidence answers for human review, (4) Abstention - model "
                        "trained to say 'I don't have enough information' rather than guess.",
                "mediocre": "Use a good prompt that says 'don't hallucinate'.",
                "why": "In legal context, a single hallucination can cause malpractice. "
                       "You need defense in depth, not just prompt engineering.",
            },
        ],
        "scaling": {
            "good": [
                "10M docs x avg 50 chunks = 500M vectors. Need sharded vector DB (Pinecone/Qdrant cluster)",
                "Tiered storage: hot (recent/frequent) in memory, warm in SSD, cold in object storage",
                "Caching layer: query-result cache with TTL, semantic cache for similar queries",
                "Async ingestion pipeline with backpressure for new document processing",
                "Read replicas for retrieval, separate write path for ingestion",
            ],
            "mediocre": ["Just use a bigger instance", "Add more RAM"],
        },
        "tradeoffs": [
            "Accuracy vs Latency: More retrieval passes = better accuracy but slower",
            "Cost vs Quality: GPT-4 for generation vs fine-tuned smaller model",
            "Freshness vs Consistency: Real-time indexing vs batch (affects vector index quality)",
            "Chunk size: Smaller = more precise retrieval, larger = more context for LLM",
        ],
    },
    {
        "title": "Design a real-time AI content moderation system for 1B posts/day",
        "context": "A social media platform needs to moderate 1 billion posts per day "
                   "using AI. Content includes text, images, and short videos. Must handle "
                   "multiple languages and cultural contexts.",
        "requirements": {
            "good_questions": [
                "What's the latency requirement? Block before publish or flag after?",
                "What content types - text only or multimodal (images, video, audio)?",
                "What violation categories - hate speech, nudity, violence, spam, misinformation?",
                "What's the false positive tolerance? (Over-moderation kills engagement)",
                "Appeals process - how quickly must we respond?",
                "Regional requirements - different rules for different jurisdictions?",
                "What's the human review capacity? (bottleneck for edge cases)",
                "Adversarial resistance - how sophisticated are bad actors?",
            ],
            "mediocre_questions": [
                "What ML model should we use?",
                "What's the tech stack?",
            ],
            "why": "Content moderation is fundamentally a product + policy problem. "
                   "Technical architecture follows from understanding the constraints.",
        },
        "architecture": {
            "good": {
                "components": [
                    "Multi-stage Pipeline: Fast classifier (sub-10ms) -> detailed model "
                    "(sub-100ms) -> human review queue for edge cases",
                    "Modality-specific Models: Text (multilingual transformer), Image (vision "
                    "model), Video (frame sampling + temporal model), Multimodal fusion",
                    "Policy Engine: Rule-based overrides, jurisdiction-specific policies, "
                    "configurable thresholds per content type",
                    "Feedback System: Human reviewer decisions -> model retraining, "
                    "appeal outcomes -> threshold adjustment",
                    "Adversarial Defense: Known attack pattern detection, periodic red-teaming, "
                    "model ensemble to resist targeted attacks",
                ],
                "diagram": textwrap.dedent("""
                    Content Submission
                        |
                    [Hash Check] -- known bad content (perceptual hash)
                        |
                    [Fast Classifier] -- lightweight model, <10ms
                    /       |       \\
                [PASS]  [REVIEW]  [BLOCK]
                    |       |
                    |   [Detailed Model] -- heavy model, <100ms
                    |   /       |       \\
                    | [PASS] [QUEUE]  [BLOCK]
                    |           |
                    |   [Human Review]
                    |   /       \\
                    v [PASS]  [BLOCK]
                    PUBLISH
                """),
            },
            "mediocre": {
                "components": [
                    "Run all content through a big AI model",
                    "If it's bad, block it",
                    "Have humans check appeals",
                ],
                "why": "Ignores latency constraints, cost at scale, adversarial attacks, "
                       "and the critical multi-stage approach needed for 1B posts/day.",
            },
        },
        "deep_dives": [
            {
                "topic": "Handling 1B posts/day at low latency",
                "good": "11,500 posts/second sustained. Fast path: lightweight model on GPU "
                        "cluster with batch inference (high throughput). Only 5-10% go to "
                        "expensive detailed model. Use model distillation for fast classifier. "
                        "Geographic distribution for latency. Async processing for video "
                        "(allow publish, flag retroactively if needed).",
                "mediocre": "Use auto-scaling.",
                "why": "At this scale, architecture IS the solution. You need to think about "
                       "throughput, batching, tiered processing, and cost management.",
            },
            {
                "topic": "Adversarial Robustness",
                "good": "Ensemble of models (harder to attack all simultaneously). Regular "
                        "adversarial training with red team outputs. Unicode normalization and "
                        "homoglyph detection for text evasion. Watermark detection for AI-generated "
                        "content. Behavioral signals (account age, post velocity) as additional "
                        "features. Honeypot deployment to detect new attack patterns.",
                "mediocre": "Train on more data.",
                "why": "Adversaries actively probe and adapt. Static models get bypassed within "
                       "weeks. You need a dynamic defense posture.",
            },
        ],
        "scaling": {
            "good": [
                "Partition by content type: text pipeline, image pipeline, video pipeline",
                "GPU cluster with batch inference for throughput (not individual requests)",
                "Model serving: TensorRT/ONNX optimized, quantized for fast inference",
                "Queue-based architecture with priority lanes (reported content = high priority)",
                "Circuit breakers: if model service degrades, fall back to rules-only",
            ],
            "mediocre": ["Add more GPUs", "Use a faster model"],
        },
        "tradeoffs": [
            "Precision vs Recall: Over-blocking (censorship concerns) vs under-blocking (harm)",
            "Latency vs Accuracy: Pre-publish blocking vs post-publish flagging",
            "Cost vs Coverage: Every post through heavy model vs tiered approach",
            "Global vs Local: One model for all cultures vs per-region models",
        ],
    },
    {
        "title": "Design an AI-powered customer support platform",
        "context": "An e-commerce company with 50M customers wants to build an AI-first "
                   "customer support system. Currently handles 200K tickets/day with 2000 "
                   "human agents. Goal: resolve 70% of tickets without human intervention.",
        "requirements": {
            "good_questions": [
                "What are the top ticket categories? (Returns, shipping, billing, product questions)",
                "What systems does the AI need to access? (Order DB, inventory, payments, shipping)",
                "What actions can the AI take autonomously? (Refund up to $X, reschedule delivery?)",
                "What's the escalation path when AI can't resolve?",
                "How do we measure 'resolved'? (Customer confirms, or no follow-up in 24h?)",
                "Multi-turn conversation support? (context across messages)",
                "What channels - chat, email, phone, social media?",
                "Compliance requirements for handling payment info?",
            ],
            "mediocre_questions": [
                "What LLM should we use?",
                "How many concurrent users?",
            ],
            "why": "Customer support is an agentic system. The key questions are about "
                   "tool access, action authority, and handoff design.",
        },
        "architecture": {
            "good": {
                "components": [
                    "Intent Router: Classify ticket into category + urgency, route to "
                    "appropriate agent (AI or human specialist)",
                    "Agentic Core: LLM with tool-use capabilities - can query orders, "
                    "check shipping, process refunds within policy limits",
                    "Policy Engine: Guardrails on what AI can do autonomously vs needs "
                    "human approval (refund limits, account changes, legal issues)",
                    "Context Manager: Maintains conversation state, customer history, "
                    "previous interactions, sentiment tracking",
                    "Escalation System: Warm handoff to human with full context summary, "
                    "AI-assisted human responses for complex cases",
                    "Quality & Learning: Every resolution scored, low-confidence flagged "
                    "for review, successful patterns feed back into training",
                ],
                "diagram": textwrap.dedent("""
                    Customer Message
                        |
                    [Channel Adapter] -- normalize from chat/email/phone
                        |
                    [Intent Classification + Entity Extraction]
                        |
                    [Policy Check] -- can AI handle this category?
                    /           \\
                [AI Agent]    [Human Queue] (with AI-suggested response)
                    |
                [Tool Selection]
                /   |   |   \\
                [Orders] [Shipping] [Payments] [Knowledge Base]
                    |
                [Response Generation]
                    |
                [Safety Check] -- PII, tone, accuracy
                    |
                [Send + Monitor Satisfaction]
                """),
            },
            "mediocre": {
                "components": [
                    "Put a chatbot on the website",
                    "Connect it to GPT-4 with our FAQ",
                    "If it can't answer, transfer to human",
                ],
                "why": "Missing: tool integration, policy limits, context management, "
                       "quality loops, multi-channel support, escalation design.",
            },
        },
        "deep_dives": [
            {
                "topic": "Tool Use and Action Authority",
                "good": "Define action tiers: Tier 1 (AI autonomous) - lookup order status, "
                        "provide tracking, answer product questions. Tier 2 (AI with limits) - "
                        "issue refund < $50, extend return window by 7 days. Tier 3 (human "
                        "approval) - refund > $50, account closure, legal claims. Implement "
                        "as a policy-as-code engine that's auditable and version-controlled.",
                "mediocre": "Let the AI decide what to do based on the conversation.",
                "why": "Uncontrolled AI actions = financial risk + customer trust issues. "
                       "Clear authority boundaries are essential for production AI agents.",
            },
            {
                "topic": "Measuring Success and Continuous Improvement",
                "good": "Multi-signal resolution detection: explicit confirmation, CSAT survey, "
                        "no re-contact within 72h, no escalation request. Track: resolution rate "
                        "by category, AI confidence vs actual outcome, escalation reasons "
                        "(new training data), cost per resolution (AI vs human), customer effort "
                        "score. Weekly model updates from human-reviewed escalations.",
                "mediocre": "Track how many tickets the AI closes.",
                "why": "A ticket 'closed' doesn't mean 'resolved'. Need multi-dimensional "
                       "quality metrics to avoid gaming a single number.",
            },
        ],
        "scaling": {
            "good": [
                "Separate read path (knowledge lookup) from write path (actions)",
                "Cache common query-response pairs (shipping status template responses)",
                "Async tool calls with optimistic response streaming",
                "Priority queuing: VIP customers, time-sensitive issues (delivery today)",
                "Graceful degradation: if LLM is slow, serve cached responses for common queries",
            ],
            "mediocre": ["Scale the LLM endpoint", "Add more API calls"],
        },
        "tradeoffs": [
            "Automation Rate vs Quality: Pushing for 90% auto-resolve risks bad resolutions",
            "Response Speed vs Accuracy: Fast template response vs careful tool-using response",
            "Cost per ticket: $0.10 (AI) vs $5 (human) - but bad AI resolution costs $15 (re-contact + angry customer)",
            "Personalization vs Privacy: More context = better responses but more data exposure",
        ],
    },
    {
        "title": "Design a multi-model AI gateway for an enterprise",
        "context": "A Fortune 500 company wants to standardize AI access across 500+ "
                   "engineering teams. Currently teams use different providers (OpenAI, "
                   "Anthropic, Google, open-source) with no governance. Need a unified "
                   "gateway with cost control, security, and observability.",
        "requirements": {
            "good_questions": [
                "What's the current monthly spend across all teams? (Likely untracked)",
                "What governance requirements - PII filtering, prompt logging, data residency?",
                "Do teams need model-specific features or can we abstract behind a common API?",
                "What's the latency budget? (Gateway adds overhead)",
                "Failover requirements? (If OpenAI is down, auto-route to Anthropic?)",
                "Budget allocation model - per-team quotas, chargebacks, shared pool?",
                "What about fine-tuned models and custom deployments?",
                "Compliance: do we need to log all prompts? Retain for how long?",
            ],
            "mediocre_questions": [
                "Which model is best?",
                "Should we use open-source or proprietary?",
            ],
            "why": "This is a platform problem, not a model selection problem. "
                   "The architecture must serve 500 teams with different needs.",
        },
        "architecture": {
            "good": {
                "components": [
                    "API Gateway Layer: Unified API (OpenAI-compatible), authentication, "
                    "rate limiting, request routing",
                    "Policy Engine: PII detection/redaction, content filtering, "
                    "prompt injection detection, data classification",
                    "Router: Model selection (cost/quality/latency optimization), "
                    "failover logic, A/B testing support, semantic caching",
                    "Cost Management: Per-team budgets, token tracking, cost allocation, "
                    "alerts, spend forecasting",
                    "Observability: Latency tracking, error rates, token usage, "
                    "quality metrics, audit logging",
                    "Model Registry: Available models, capabilities, pricing, SLAs, "
                    "deprecation schedules",
                ],
                "diagram": textwrap.dedent("""
                    Team Applications (500+ services)
                        |
                    [API Gateway] -- auth, rate limit, routing
                        |
                    [Policy Engine] -- PII redaction, content filter
                        |
                    [Semantic Cache] -- hit? return cached
                        |
                    [Smart Router] -- model selection, load balancing
                    /    |    |    \\
                [OpenAI] [Anthropic] [Google] [Self-hosted]
                        |
                    [Response Post-processing] -- PII check output
                        |
                    [Observability] -- log, metrics, cost tracking
                        |
                    Response to Application
                """),
            },
            "mediocre": {
                "components": [
                    "Put a proxy in front of OpenAI",
                    "Add API keys per team",
                    "Log the requests",
                ],
                "why": "This is just a reverse proxy, not a platform. Missing: policy "
                       "enforcement, smart routing, cost management, failover, caching.",
            },
        },
        "deep_dives": [
            {
                "topic": "Smart Routing and Failover",
                "good": "Route based on: (1) Request characteristics - simple queries to "
                        "cheaper/faster models, complex reasoning to GPT-4/Claude, "
                        "(2) Team preferences and SLAs, (3) Current provider health "
                        "(circuit breaker pattern), (4) Cost optimization (route to cheapest "
                        "model meeting quality threshold). Failover: detect degradation via "
                        "latency percentiles, automatic reroute with prompt adaptation "
                        "(different models need different prompts).",
                "mediocre": "Round-robin between providers.",
                "why": "Models aren't interchangeable. Smart routing needs to understand "
                       "model capabilities, costs, and current health.",
            },
            {
                "topic": "Security and Compliance",
                "good": "Layered approach: (1) Input scanning - PII detection with NER, "
                        "regex for structured data (SSN, CC#), custom patterns per team. "
                        "(2) Prompt injection detection - classifier trained on known attacks. "
                        "(3) Output scanning - ensure model didn't leak training data or "
                        "other teams' context. (4) Audit trail - every request logged with "
                        "team, user, model, tokens, but PII redacted from logs. "
                        "(5) Data residency - route EU data to EU-hosted models only.",
                "mediocre": "Encrypt the API keys and use HTTPS.",
                "why": "Enterprise AI governance is multi-dimensional. Just securing "
                       "transport doesn't address data handling, compliance, or abuse.",
            },
        ],
        "scaling": {
            "good": [
                "Stateless gateway nodes behind load balancer (horizontal scale)",
                "Async logging pipeline (don't block requests for observability)",
                "Distributed rate limiting (Redis-based token bucket per team)",
                "Connection pooling to providers (avoid per-request TLS handshake)",
                "Multi-region deployment for latency and data residency",
            ],
            "mediocre": ["Use a bigger server", "Scale vertically"],
        },
        "tradeoffs": [
            "Abstraction vs Power: Unified API hides model-specific features",
            "Latency vs Safety: PII scanning adds 10-50ms per request",
            "Caching vs Freshness: Semantic cache saves cost but may serve stale responses",
            "Control vs Autonomy: Strict governance vs letting teams experiment freely",
        ],
    },
    {
        "title": "Design a recommendation system using LLMs",
        "context": "A streaming platform (50M users, 500K content items) wants to "
                   "augment their traditional recommendation system with LLM-based "
                   "understanding. Users complain recommendations are 'more of the same' - "
                   "want serendipitous, explainable recommendations.",
        "requirements": {
            "good_questions": [
                "What's the current rec system? (Collaborative filtering? Content-based?)",
                "What signals do we have? (Watch history, ratings, search, time-of-day, device?)",
                "What does 'serendipitous' mean here? (Cross-genre? Emerging content? Niche?)",
                "Latency budget for recommendations? (Homepage load vs. 'explore' page?)",
                "Cold start problem - new users and new content?",
                "A/B testing infrastructure - how do we measure if LLM recs are better?",
                "What's the cost budget per recommendation request?",
                "Do users want explanations? ('Because you watched X' style?)",
            ],
            "mediocre_questions": [
                "What LLM should we use?",
                "Should we fine-tune?",
            ],
            "why": "Recommendation is a product problem. Understanding what 'better' means "
                   "and what signals are available drives the architecture.",
        },
        "architecture": {
            "good": {
                "components": [
                    "User Understanding Layer: LLM-generated user taste profiles from "
                    "watch history narratives ('likes slow-burn thrillers with complex characters')",
                    "Content Understanding Layer: LLM-generated rich content metadata "
                    "(themes, mood, narrative style - beyond genre tags)",
                    "Candidate Generation: Traditional system generates 1000 candidates, "
                    "LLM-enhanced features for re-ranking",
                    "LLM Re-ranker: Takes top-100 candidates, user profile, and context - "
                    "re-ranks with explanation generation",
                    "Exploration Module: LLM identifies 'adjacent interests' for serendipity "
                    "('you like noir thrillers, you might enjoy Nordic crime drama')",
                    "Explanation Generator: Natural language explanations for each recommendation",
                ],
                "diagram": textwrap.dedent("""
                    User Request (homepage load)
                        |
                    [User Profile Service] -- taste narrative + behavior signals
                        |
                    [Candidate Generation] -- traditional ML, 1000 candidates
                        |
                    [Feature Enrichment] -- add LLM-generated content features
                        |
                    [LLM Re-ranker] -- score with user taste alignment
                        |
                    [Exploration Injection] -- 10-20% serendipitous picks
                        |
                    [Explanation Generation] -- why each recommendation
                        |
                    [A/B Framework] -- measure engagement lift
                        |
                    Final Ranked List + Explanations
                """),
            },
            "mediocre": {
                "components": [
                    "Send user's watch history to GPT-4",
                    "Ask it to recommend similar content",
                    "Show the recommendations",
                ],
                "why": "Won't scale to 50M users (cost), ignores existing system value, "
                       "no offline/online split, no measurement framework.",
            },
        },
        "deep_dives": [
            {
                "topic": "Cost Management for LLM-enhanced Recs at Scale",
                "good": "Offline pre-computation: Generate user taste profiles daily (batch), "
                        "generate content metadata on ingestion (one-time). Online: only use "
                        "LLM for re-ranking top-100 (not all 500K items). Cache explanations "
                        "for popular items per user segment. Use distilled smaller model for "
                        "real-time, GPT-4 for offline enrichment. Cost: ~$0.001 per rec request "
                        "with this architecture vs $0.10 if naive.",
                "mediocre": "Use a cheaper model.",
                "why": "At 50M users x multiple rec requests/day, even $0.01/request = "
                       "$500K/day. Architecture must separate offline enrichment from online serving.",
            },
            {
                "topic": "Measuring Serendipity",
                "good": "Define metrics: (1) Intra-list diversity (genre/theme spread), "
                        "(2) Surprise factor (how far from user's typical consumption), "
                        "(3) Discovery rate (% of recs from content user wouldn't have found), "
                        "(4) Engagement on surprising recs (did serendipity actually work?). "
                        "A/B test: control (current system) vs treatment (LLM-enhanced). "
                        "Guard metric: ensure overall engagement doesn't drop while increasing "
                        "diversity.",
                "mediocre": "See if users watch more content.",
                "why": "Serendipity without engagement is just bad recommendations. "
                       "Need to measure both novelty AND satisfaction.",
            },
        ],
        "scaling": {
            "good": [
                "Offline-heavy architecture: LLM calls in batch jobs, not real-time path",
                "Pre-computed embeddings and taste profiles refreshed daily",
                "Real-time path uses lightweight model (distilled from LLM teacher)",
                "Feature store for LLM-generated content metadata (compute once, serve many)",
                "Tiered approach: heavy personalization for active users, lightweight for casual",
            ],
            "mediocre": ["Cache the LLM responses", "Use a faster model"],
        },
        "tradeoffs": [
            "Serendipity vs Relevance: Too surprising = bad, too safe = boring",
            "Offline vs Online: Pre-computed = stale but cheap, real-time = fresh but expensive",
            "Explainability vs Privacy: Good explanations reveal what data you're using",
            "LLM sophistication vs Latency: Better understanding vs page load time",
        ],
    },
]

# ============================================================================
# SCORING RUBRIC
# ============================================================================

SCORING_RUBRIC = {
    "Senior Engineer": {
        "requirements": "Asks functional requirements, maybe some scale questions",
        "architecture": "Correct components but may miss non-obvious ones (caching, feedback loops)",
        "deep_dive": "Can go deep on ONE component, struggles to connect to system-wide impact",
        "scaling": "Knows common patterns (sharding, caching) but applies them generically",
        "tradeoffs": "Identifies 1-2 tradeoffs but picks one side without nuance",
        "score_range": "3.0 - 3.5 / 5.0",
    },
    "Staff Engineer": {
        "requirements": "Asks questions that REVEAL hidden constraints and change the design",
        "architecture": "Complete system with feedback loops, observability, failure modes",
        "deep_dive": "Goes deep AND connects back to system properties (latency, cost, reliability)",
        "scaling": "Identifies THE bottleneck and designs specifically for it",
        "tradeoffs": "Frames as 'it depends on X' and shows how different choices lead to different architectures",
        "score_range": "3.5 - 4.5 / 5.0",
    },
    "Principal Engineer": {
        "requirements": "Reframes the problem ('you said X but the real problem is Y')",
        "architecture": "Designs for evolution - shows v1 vs v2, what to defer, where to invest",
        "deep_dive": "Connects technical depth to business outcomes and organizational constraints",
        "scaling": "Thinks about operational complexity, not just throughput",
        "tradeoffs": "Shows organizational tradeoffs (team topology, build vs buy, migration strategy)",
        "score_range": "4.5 - 5.0 / 5.0",
    },
}

# ============================================================================
# DISPLAY HELPERS
# ============================================================================

def print_header(text, char="="):
    width = 78
    print(f"\n{char * width}")
    print(f" {text}")
    print(f"{char * width}")


def print_subheader(text):
    print(f"\n{'─' * 60}")
    print(f"  {text}")
    print(f"{'─' * 60}")


def print_comparison(good_label, good_content, bad_label, bad_content, explanation):
    print(f"\n  {'GOOD ANSWER':^36} | {'MEDIOCRE ANSWER':^36}")
    print(f"  {'─' * 36} | {'─' * 36}")

    if isinstance(good_content, list):
        max_lines = max(len(good_content), len(bad_content) if isinstance(bad_content, list) else 1)
        for i in range(max_lines):
            g = good_content[i] if i < len(good_content) else ""
            b = bad_content[i] if isinstance(bad_content, list) and i < len(bad_content) else (bad_content if i == 0 and not isinstance(bad_content, list) else "")
            g_wrapped = textwrap.shorten(g, width=36, placeholder="...")
            b_wrapped = textwrap.shorten(b, width=36, placeholder="...")
            print(f"  {g_wrapped:<36} | {b_wrapped:<36}")
    else:
        for line in textwrap.wrap(good_content, width=36):
            print(f"  {line:<36} |")
        print(f"  {'─' * 36} |")
        for line in textwrap.wrap(bad_content, width=36):
            print(f"  {'':36} | {line}")

    print(f"\n  WHY: {explanation}")


def print_bullet_list(items, indent=4):
    for item in items:
        wrapped = textwrap.wrap(item, width=74 - indent)
        print(f"{' ' * indent}* {wrapped[0]}")
        for line in wrapped[1:]:
            print(f"{' ' * indent}  {line}")


def pause(seconds=1):
    time.sleep(seconds)


# ============================================================================
# MAIN SIMULATION
# ============================================================================

def run_simulation():
    print_header("AI SYSTEM DESIGN INTERVIEW SIMULATOR")
    print("\n  This simulator walks you through a system design interview")
    print("  showing what GOOD and MEDIOCRE answers look like at each stage.")
    print("  Use this to calibrate your responses for Staff+ interviews.\n")

    # Pick a random scenario
    scenario = random.choice(SCENARIOS)

    print_header(f"PROBLEM: {scenario['title']}", "~")
    print(f"\n  Context: {scenario['context']}\n")
    pause()

    # ─── Phase 1: Requirements ───
    print_header("PHASE 1: REQUIREMENTS GATHERING (5-8 minutes)", "-")
    print("\n  What interviewers assess: Do you ask questions that CHANGE the design?")
    print("  Or do you ask generic questions that any engineer would ask?\n")

    print_subheader("GOOD Questions (reveal constraints)")
    print_bullet_list(scenario["requirements"]["good_questions"])

    print_subheader("MEDIOCRE Questions (generic, don't inform design)")
    print_bullet_list(scenario["requirements"]["mediocre_questions"])

    print(f"\n  INSIGHT: {scenario['requirements']['why']}")
    pause()

    # ─── Phase 2: Architecture ───
    print_header("PHASE 2: HIGH-LEVEL ARCHITECTURE (10-15 minutes)", "-")
    print("\n  What interviewers assess: Do you have a COMPLETE system view?")
    print("  Or just the happy path?\n")

    print_subheader("GOOD Architecture - Key Components")
    print_bullet_list(scenario["architecture"]["good"]["components"])

    print_subheader("Architecture Diagram (what you'd draw on whiteboard)")
    print(scenario["architecture"]["good"]["diagram"])

    print_subheader("MEDIOCRE Architecture")
    print_bullet_list(scenario["architecture"]["mediocre"]["components"])
    print(f"\n  WHY IT'S MEDIOCRE: {scenario['architecture']['mediocre']['why']}")
    pause()

    # ─── Phase 3: Deep Dives ───
    print_header("PHASE 3: DEEP DIVES (10-15 minutes)", "-")
    print("\n  What interviewers assess: Can you go deep AND connect back to the system?")
    print("  Staff+ engineers show depth that informs system-wide decisions.\n")

    for dd in scenario["deep_dives"]:
        print_subheader(f"Deep Dive: {dd['topic']}")
        print(f"\n  GOOD Answer:")
        for line in textwrap.wrap(dd["good"], width=72):
            print(f"    {line}")
        print(f"\n  MEDIOCRE Answer:")
        for line in textwrap.wrap(dd["mediocre"], width=72):
            print(f"    {line}")
        print(f"\n  WHY: {dd['why']}")
        pause()

    # ─── Phase 4: Scaling ───
    print_header("PHASE 4: SCALING CONSIDERATIONS (5-8 minutes)", "-")
    print("\n  What interviewers assess: Do you identify THE bottleneck?")
    print("  Or just list generic scaling patterns?\n")

    print_subheader("GOOD Scaling Discussion")
    print_bullet_list(scenario["scaling"]["good"])

    print_subheader("MEDIOCRE Scaling Discussion")
    print_bullet_list(scenario["scaling"]["mediocre"])
    pause()

    # ─── Phase 5: Tradeoffs ───
    print_header("PHASE 5: TRADE-OFFS (5 minutes)", "-")
    print("\n  What interviewers assess: Can you hold multiple options in mind")
    print("  and articulate WHEN each is appropriate?\n")

    print_subheader("Key Trade-offs to Discuss")
    print_bullet_list(scenario["tradeoffs"])
    pause()

    # ─── Scoring Rubric ───
    print_header("SCORING RUBRIC: How Interviewers Evaluate", "=")
    print()
    for level, criteria in SCORING_RUBRIC.items():
        print_subheader(f"{level} ({criteria['score_range']})")
        for phase, description in criteria.items():
            if phase != "score_range":
                print(f"    {phase.upper():12s}: {description}")
        print()

    # ─── Summary ───
    print_header("KEY TAKEAWAYS FOR YOUR PREP")
    print("""
    1. Requirements phase is NOT a formality - it's where you show product sense
    2. Architecture should include feedback loops, failure modes, observability
    3. Deep dives should connect technical choices to business outcomes
    4. Scaling = identify THE bottleneck, not list every pattern you know
    5. Tradeoffs = show you can hold complexity, not just pick one option

    STAFF vs SENIOR difference:
    - Senior: "Here's how to build it" (correct implementation)
    - Staff:  "Here's WHY to build it this way, and what changes if X" (design reasoning)
    - Principal: "Here's the v1 that gets us learning, and the v2 architecture" (strategic)
    """)

    print_header("END OF SIMULATION")
    print(f"\n  Scenario practiced: {scenario['title']}")
    print(f"  Run again for a different scenario (5 total).\n")


if __name__ == "__main__":
    run_simulation()
