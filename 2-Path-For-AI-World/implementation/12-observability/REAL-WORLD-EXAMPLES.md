# Real-World Examples: AI Observability

## Case Study 1: Debugging a Production RAG Pipeline with LangSmith

**Company:** Enterprise SaaS with a RAG-powered documentation assistant. Users reported "the AI gives wrong answers about pricing" — but only sometimes.

### The Trace That Revealed the Bug

Using LangSmith, the team filtered traces by: `user_feedback == "negative" AND topic == "pricing"`.

```
Trace ID: run_8f3a2c1d-4e5b-6789-abcd-ef0123456789
Timestamp: 2024-03-12T14:23:17Z
Total duration: 4.2s
Total cost: $0.087

├── [Retrieval] duration=890ms
│   ├── Query: "What is the enterprise plan pricing?"
│   ├── Rewritten query: "enterprise plan cost price tier"
│   ├── Retrieved chunks (top-5):
│   │   ├── chunk_1: "Enterprise plan starts at $499/month..." (score: 0.91) ← CORRECT (2024 pricing page)
│   │   ├── chunk_2: "Enterprise tier: $299/month per seat..." (score: 0.89) ← WRONG (2022 archived page!)
│   │   ├── chunk_3: "For enterprise customers, contact sales..." (score: 0.86)
│   │   ├── chunk_4: "Enterprise features include SSO, SAML..." (score: 0.84)
│   │   └── chunk_5: "Pricing is subject to change..." (score: 0.81)
│   └── Metadata: { source_urls, last_indexed_dates, document_types }
│
├── [LLM Generation] duration=3.1s, model=gpt-4, tokens_in=2847, tokens_out=186
│   ├── System: "Answer based only on provided context..."
│   ├── Context: [5 chunks above]
│   ├── Response: "Enterprise plan pricing is $299/month per seat..."  ← WRONG!
│   └── Note: Model chose chunk_2 because it had more specific pricing detail
│
└── [Post-processing] duration=210ms
    ├── Guardrail check: PASSED
    ├── Citation extraction: cited chunk_2
    └── Confidence: 0.84
```

### Root Cause

The vector store contained **two versions** of the pricing page:
- Current (2024): `$499/month` — indexed from live docs
- Archived (2022): `$299/month` — indexed from a Wayback Machine crawl someone accidentally included

Both had high semantic similarity to pricing queries. The model sometimes picked the wrong one because the archived version had more detailed pricing breakdowns.

### Fix Applied

```python
# Added metadata filter to exclude archived documents
retriever_config = {
    "filter": {
        "document_status": "current",
        "last_verified_date": {"$gte": "2024-01-01"}
    },
    "boost": {
        "source_type": {"official_docs": 1.2, "blog": 0.8, "archive": 0.0}
    }
}
```

### LangSmith Dashboard Setup for Ongoing Monitoring

```python
# Automated evaluation on traces
from langsmith import Client

client = Client()

# Create dataset from known-good Q&A pairs
dataset = client.create_dataset("pricing_qa_golden")
client.create_examples(
    inputs=[{"question": "What is enterprise pricing?"}],
    outputs=[{"answer": "Enterprise plan starts at $499/month"}],
    dataset_id=dataset.id
)

# Run evaluation weekly
results = client.run_on_dataset(
    dataset_name="pricing_qa_golden",
    llm_or_chain=rag_chain,
    evaluation=["correctness", "relevance"],
)
```

---

## Case Study 2: Building an AI Observability Stack from Scratch

**Company:** Platform team at a Series D startup with 12 AI-powered features across 4 product teams.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Application Layer                                           │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          │
│  │ Chat Bot│ │ Search  │ │ Summarize│ │ Code Gen│          │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘          │
│       │            │            │            │               │
│       └────────────┴────────────┴────────────┘               │
│                          │                                    │
│              ┌───────────┴───────────┐                       │
│              │  AI Gateway (custom)   │                       │
│              │  - OpenTelemetry spans │                       │
│              │  - Cost tracking       │                       │
│              │  - Rate limiting       │                       │
│              └───────────┬───────────┘                       │
└──────────────────────────┼───────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              │  OpenTelemetry Collector │
              │  - Sampling decisions    │
              │  - Attribute enrichment  │
              │  - Export to backends    │
              └─────┬──────────┬────────┘
                    │          │
         ┌──────────┘          └──────────┐
         ▼                                 ▼
┌─────────────────┐              ┌─────────────────┐
│  Tempo (traces) │              │  Prometheus     │
│  30-day retain  │              │  (metrics)      │
└────────┬────────┘              └────────┬────────┘
         │                                 │
         └──────────┐          ┌───────────┘
                    ▼          ▼
              ┌─────────────────────┐
              │   Grafana Dashboards │
              │   + Alerting         │
              └─────────────────────┘
```

### Custom OpenTelemetry Instrumentation

```python
from opentelemetry import trace
from opentelemetry.trace import SpanKind
import time

tracer = trace.get_tracer("ai-gateway")

class InstrumentedAIGateway:
    async def call_llm(self, request: LLMRequest) -> LLMResponse:
        with tracer.start_as_current_span(
            "llm.call",
            kind=SpanKind.CLIENT,
            attributes={
                "ai.model": request.model,
                "ai.provider": request.provider,
                "ai.feature": request.feature_name,
                "ai.user_id": request.user_id,
                "ai.request.tokens.estimated": self.estimate_tokens(request),
                "ai.request.temperature": request.temperature,
                "ai.request.max_tokens": request.max_tokens,
            }
        ) as span:
            start = time.monotonic()
            
            try:
                response = await self.provider_client.complete(request)
                
                # Add response attributes
                span.set_attribute("ai.response.tokens.input", response.usage.input_tokens)
                span.set_attribute("ai.response.tokens.output", response.usage.output_tokens)
                span.set_attribute("ai.response.tokens.total", response.usage.total_tokens)
                span.set_attribute("ai.response.cost_usd", self.calculate_cost(request.model, response.usage))
                span.set_attribute("ai.response.finish_reason", response.finish_reason)
                span.set_attribute("ai.response.latency_ms", (time.monotonic() - start) * 1000)
                
                # Time to first token (for streaming)
                if hasattr(response, "first_token_ms"):
                    span.set_attribute("ai.response.ttft_ms", response.first_token_ms)
                
                return response
                
            except Exception as e:
                span.set_attribute("ai.error.type", type(e).__name__)
                span.set_attribute("ai.error.message", str(e))
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                raise
    
    async def call_retrieval(self, query: str, config: RetrievalConfig):
        with tracer.start_as_current_span(
            "retrieval.search",
            attributes={
                "retrieval.query": query[:200],  # Truncate for storage
                "retrieval.top_k": config.top_k,
                "retrieval.collection": config.collection_name,
                "retrieval.filter": json.dumps(config.metadata_filter),
            }
        ) as span:
            results = await self.vector_store.search(query, config)
            
            span.set_attribute("retrieval.results_count", len(results))
            span.set_attribute("retrieval.top_score", results[0].score if results else 0)
            span.set_attribute("retrieval.min_score", results[-1].score if results else 0)
            span.set_attribute("retrieval.avg_chunk_tokens", 
                             sum(r.token_count for r in results) / len(results) if results else 0)
            
            return results
```

### Grafana Dashboard JSON (Key Panels)

```json
{
  "panels": [
    {
      "title": "AI Cost Rate ($/hour)",
      "type": "timeseries",
      "targets": [{
        "expr": "sum(rate(ai_request_cost_usd_total[5m])) * 3600",
        "legendFormat": "Total $/hour"
      }]
    },
    {
      "title": "P95 Latency by Model",
      "type": "timeseries", 
      "targets": [{
        "expr": "histogram_quantile(0.95, rate(ai_response_latency_ms_bucket[5m]))",
        "legendFormat": "{{model}} p95"
      }]
    },
    {
      "title": "Error Rate by Provider",
      "type": "stat",
      "targets": [{
        "expr": "sum(rate(ai_request_errors_total[5m])) / sum(rate(ai_requests_total[5m])) * 100"
      }]
    }
  ]
}
```

---

## Case Study 3: Distributed Tracing for a 5-Tool Agent

**Scenario:** A research agent that answers complex questions by orchestrating multiple tools.

### Full Trace Visualization

```
Trace ID: agent_trace_7a8b9c0d
User Query: "Compare Q3 2024 revenue of Microsoft, Google, and Apple and explain growth trends"
Total Duration: 18.7s | Total Cost: $0.34 | Total LLM Calls: 7

├── [Agent Planning] 1.2s | GPT-4 | $0.045
│   ├── Input: User query + available tools description
│   ├── Output: Plan with 3 parallel searches + 1 analysis + 1 synthesis
│   └── Tokens: 890 in / 245 out
│
├── [Tool: web_search] 2.1s (parallel group 1)
│   ├── Query: "Microsoft Q3 2024 revenue earnings report"
│   ├── Results: 8 URLs fetched, 3 selected
│   └── Content extracted: 1,847 tokens
│
├── [Tool: web_search] 1.8s (parallel group 1)
│   ├── Query: "Google Alphabet Q3 2024 revenue"
│   ├── Results: 6 URLs fetched, 3 selected
│   └── Content extracted: 1,623 tokens
│
├── [Tool: web_search] 2.3s (parallel group 1)
│   ├── Query: "Apple Q3 2024 revenue fiscal results"
│   ├── Results: 7 URLs fetched, 2 selected
│   └── Content extracted: 1,412 tokens
│
├── [Tool: calculator] 0.3s
│   ├── Input: Revenue numbers for YoY growth calculation
│   ├── Computation: Growth rates for each company
│   └── Output: Structured comparison table
│
├── [Agent Reasoning] 3.8s | GPT-4 | $0.12
│   ├── Input: All tool outputs + original query (6,200 tokens)
│   ├── Output: Structured analysis (1,100 tokens)
│   └── Reasoning: Compared growth, identified trends
│
├── [Tool: chart_generator] 1.4s
│   ├── Input: Revenue data series
│   ├── Output: Bar chart SVG (comparison) + line chart (trends)
│   └── Format: SVG embedded in markdown
│
└── [Agent Synthesis] 5.8s | GPT-4 | $0.16
    ├── Input: Analysis + charts + original query (4,800 tokens)
    ├── Output: Final comprehensive answer (2,400 tokens)
    └── Quality: groundedness=0.94, completeness=0.91

Timing Breakdown:
  Planning:        1.2s  (6.4%)
  Tool execution:  7.9s  (42.2%) ← bottleneck
  LLM reasoning:   9.6s  (51.3%)
  
Parallel efficiency: 
  Sequential time if no parallelism: 24.1s
  Actual time with parallel tools: 18.7s
  Savings from parallelism: 22.4%
```

### What This Trace Reveals for Optimization

```python
# Insights from trace analysis:
optimization_opportunities = {
    "tool_timeout": "web_search averages 2.1s — add 3s timeout + fallback cache",
    "parallel_expansion": "calculator depends on search results but chart_generator "
                         "could start earlier with partial data",
    "token_waste": "Agent synthesis receives 4800 tokens but produces answer "
                  "that only references ~2100 tokens of input. Pre-filter possible.",
    "caching": "Same companies queried repeatedly by different users — "
              "cache financial data for 1 hour",
}
```

---

## Case Study 4: The 4 Dashboards Every AI Team Needs

### Dashboard 1: Operations

```yaml
name: "AI Operations"
refresh: 30s
panels:
  - title: "Request Rate"
    query: "sum(rate(ai_requests_total[1m])) by (model, feature)"
    
  - title: "Error Rate"
    query: "sum(rate(ai_errors_total[5m])) / sum(rate(ai_requests_total[5m]))"
    thresholds: [warning: 1%, critical: 5%]
    
  - title: "Latency Distribution"
    query: "histogram_quantile(0.5|0.95|0.99, ai_latency_seconds_bucket)"
    
  - title: "Provider Health"
    type: "status_map"
    providers: [openai, anthropic, cohere]
    signals: [error_rate, latency_p95, rate_limit_hits]
    
  - title: "Rate Limit Proximity"
    query: "ai_rate_limit_remaining / ai_rate_limit_total"
    alert_at: 0.1  # Alert when 90% of rate limit consumed
    
  - title: "Queue Depth"
    query: "ai_request_queue_length"
    alert_at: 1000
```

### Dashboard 2: Quality

```yaml
name: "AI Quality"
refresh: 5m
panels:
  - title: "User Satisfaction (Thumbs Up Rate)"
    query: "sum(feedback_positive) / sum(feedback_total)"
    by: [feature, model]
    baseline: 0.82
    alert_below: 0.75
    
  - title: "Groundedness Score (7-day trend)"
    query: "avg(groundedness_score) by (feature)"
    type: "timeseries"
    annotation: "model_deployments"  # Show when models changed
    
  - title: "Hallucination Rate"
    query: "sum(hallucination_detected) / sum(responses_evaluated)"
    by: [category, model]
    alert_above: 0.05  # >5% hallucination rate
    
  - title: "Guardrail Trigger Rate"
    query: "sum(rate(guardrail_triggered_total[1h])) by (guardrail_type)"
    types: [toxicity, pii_leak, off_topic, refusal]
    
  - title: "Retrieval Relevance"
    query: "avg(retrieval_top_score) by (collection)"
    alert_below: 0.75  # Chunks becoming less relevant = index drift
    
  - title: "Answer Completeness (LLM-as-Judge)"
    query: "avg(completeness_score)"
    evaluated_sample: "5% of production traffic"
```

### Dashboard 3: Cost

```yaml
name: "AI Cost Intelligence"
refresh: 1m
panels:
  - title: "Daily Spend vs Budget"
    query: "sum(ai_cost_usd_total) vs $DAILY_BUDGET"
    type: "gauge"
    zones: [green: <80%, yellow: 80-95%, red: >95%]
    
  - title: "Cost per Feature"
    query: "sum(ai_cost_usd_total) by (feature)"
    type: "pie_chart"
    
  - title: "Cost per Successful Interaction"
    query: "sum(ai_cost_usd_total{outcome='success'}) / count(interactions{outcome='success'})"
    insight: "True unit economics — includes retries and failures"
    
  - title: "Token Efficiency"
    query: "avg(useful_output_tokens / total_tokens_consumed)"
    target: ">0.4"
    
  - title: "Cache Savings"
    query: "sum(cache_hits) * avg(cost_per_request)"
    type: "stat"
    label: "Money saved by caching today"
    
  - title: "Cost Anomaly Detection"
    query: "ai_cost_zscore > 3"
    type: "alert_list"
```

### Dashboard 4: User Experience

```yaml
name: "AI User Experience"
refresh: 5m
panels:
  - title: "Time to First Token (Streaming)"
    query: "histogram_quantile(0.95, ttft_seconds_bucket)"
    target: "<1.5s"
    
  - title: "End-to-End Response Time"
    query: "histogram_quantile(0.95, e2e_seconds_bucket)"
    by: [feature]
    
  - title: "Conversation Completion Rate"
    query: "conversations_completed / conversations_started"
    insight: "Do users abandon mid-conversation?"
    
  - title: "Retry/Regenerate Rate"
    query: "sum(regenerate_clicks) / sum(responses_shown)"
    alert_above: 0.15  # >15% regeneration = quality issue
    
  - title: "Feature Adoption"
    query: "unique_users_per_feature / total_active_users"
    type: "bar_chart"
    
  - title: "Error Messages Shown to Users"
    query: "sum(user_facing_errors) by (error_type)"
    types: [timeout, rate_limit, content_filter, generic_error]
```

---

## Case Study 5: Alert Design for AI Systems

### Production Alert Configuration

```yaml
# alerts.yaml — Real alert rules from a production AI system

groups:
  - name: ai_latency
    rules:
      - alert: HighP95Latency
        expr: histogram_quantile(0.95, rate(ai_latency_seconds_bucket[5m])) > 8
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "P95 latency above 8s for 5 minutes"
          runbook: "Check provider status page. If provider healthy, check if input tokens increased."
      
      - alert: CriticalLatency
        expr: histogram_quantile(0.99, rate(ai_latency_seconds_bucket[5m])) > 30
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "P99 latency above 30s — users likely timing out"
          action: "Enable fallback model routing immediately"

  - name: ai_quality
    rules:
      - alert: QualityDrift
        expr: avg_over_time(groundedness_score[1h]) < avg_over_time(groundedness_score[7d] offset 1h) * 0.9
        for: 30m
        labels:
          severity: warning
        annotations:
          summary: "Groundedness dropped >10% vs 7-day average"
          runbook: "Check recent index updates. Run retrieval quality eval on last 100 queries."
      
      - alert: HallucinationSpike
        expr: rate(hallucination_detected_total[1h]) / rate(responses_evaluated_total[1h]) > 0.08
        for: 15m
        labels:
          severity: critical
        annotations:
          summary: "Hallucination rate above 8%"
          action: "Check for corrupted documents in vector store. Review recent index updates."
      
      - alert: GuardrailTriggerSpike
        expr: rate(guardrail_triggered_total{type="pii_leak"}[15m]) > 5
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "PII leak guardrail triggering >5 times in 15min"
          action: "Investigate immediately. May indicate prompt injection attack."

  - name: ai_cost
    rules:
      - alert: HourlyBudgetExceeded
        expr: sum(increase(ai_cost_usd_total[1h])) > 500
        for: 0m  # Immediate
        labels:
          severity: critical
        annotations:
          summary: "Hourly AI spend exceeded $500 (budget: $350)"
          action: "Check for runaway loops. Enable aggressive model downgrade."
      
      - alert: CostPerRequestAnomaly
        expr: |
          avg(ai_cost_per_request) > 
          avg_over_time(ai_cost_per_request[7d]) * 2
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "Average cost/request doubled vs 7-day baseline"
```

---

## Case Study 6: Root Cause Analysis — 40% Quality Drop from One Bad Document

**Timeline of incident:**

```
Day 0: Vector store re-indexed after adding 2,400 new support articles
Day 1: Quality monitoring shows groundedness score drop: 0.89 → 0.53
Day 1+2h: Alert fires: "QualityDrift" — groundedness below threshold
Day 1+3h: On-call engineer begins investigation
```

### Investigation Using Traces

```python
# Step 1: Identify affected queries
affected_traces = langfuse.get_traces(
    filter={
        "scores.groundedness": {"$lt": 0.6},
        "timestamp": {"$gte": "2024-03-15T00:00:00Z"}
    },
    limit=200
)

# Step 2: Analyze retrieval patterns in affected traces
chunk_frequency = Counter()
for trace in affected_traces:
    retrieval_span = trace.get_span("retrieval.search")
    for chunk in retrieval_span.output["chunks"]:
        chunk_frequency[chunk["document_id"]] += 1

# Result: One document appeared in 67% of failing traces
# Document ID: doc_8f2a3b4c — "product_faq_combined_v2.html"
print(chunk_frequency.most_common(5))
# [('doc_8f2a3b4c', 134), ('doc_normal1', 12), ('doc_normal2', 8), ...]
```

### The Corrupted Document

```python
# Step 3: Examine the problematic document
doc = vector_store.get_document("doc_8f2a3b4c")
print(doc.metadata)
# {
#   "source": "product_faq_combined_v2.html",
#   "indexed_at": "2024-03-15T02:14:00Z",
#   "token_count": 89000,  # ← SUSPICIOUS! Normal docs are 500-3000 tokens
#   "chunk_count": 147     # ← This one document created 147 chunks!
# }

# The document was a concatenation of ALL FAQ pages into one HTML file
# with corrupted encoding that mixed questions with wrong answers.
# Because it had 147 chunks covering every topic, it appeared in 
# nearly every retrieval result, contaminating responses with wrong info.
```

### Fix and Prevention

```python
# Immediate fix
vector_store.delete_document("doc_8f2a3b4c")
# Quality recovered to 0.87 within 1 hour

# Prevention: Added indexing guardrails
class IndexingGuardrails:
    MAX_DOCUMENT_TOKENS = 10000
    MAX_CHUNKS_PER_DOCUMENT = 20
    
    def validate_before_index(self, document):
        if document.token_count > self.MAX_DOCUMENT_TOKENS:
            raise IndexingError(f"Document too large: {document.token_count} tokens")
        
        # Check for encoding issues
        if self.detect_encoding_corruption(document.content):
            raise IndexingError("Encoding corruption detected")
        
        # Validate that chunked content maintains semantic coherence
        chunks = self.chunker.chunk(document)
        for chunk in chunks:
            coherence = self.measure_coherence(chunk)
            if coherence < 0.5:
                raise IndexingError(f"Low coherence chunk detected: {coherence}")
```

---

## Case Study 7: Production Debugging Workflow — "Why Did the AI Give a Wrong Answer?"

**Trigger:** Customer escalation: "Your AI told me I could get a refund after 90 days, but your policy is 30 days."

### Step-by-Step Investigation

```
Step 1: Find the specific conversation
─────────────────────────────────────
Search traces by: user_id + timestamp range + keyword "refund"
Found: trace_id = "conv_2024031_usr8847_msg12"

Step 2: Examine the trace
─────────────────────────────────────
├── [User Message] "Can I get a refund? I bought this 45 days ago"
│
├── [Retrieval] 
│   ├── Query expansion: "refund policy timeframe days"
│   ├── Retrieved chunks:
│   │   ├── chunk_a: "Refund policy: Full refund within 30 days of purchase" (score: 0.93)
│   │   ├── chunk_b: "Extended warranty customers: 90-day refund window" (score: 0.90)  ← PROBLEM
│   │   ├── chunk_c: "To request a refund, contact support..." (score: 0.87)
│   │
│   └── Issue: chunk_b is from the "Extended Warranty" document but has no
│       metadata filter to indicate it only applies to warranty customers
│
├── [LLM Response]
│   ├── "Based on our policy, you have a 90-day refund window..."
│   └── The model saw TWO timeframes (30 and 90 days) and chose the more
│       generous one — likely because the user mentioned "45 days" which
│       falls within 90 but outside 30
│
└── Root Cause: Missing metadata filtering in retrieval

Step 3: Verify the hypothesis
─────────────────────────────────────
# Check: How often does chunk_b appear for non-warranty customers?
affected_conversations = langfuse.search_traces(
    filter={"retrieval.chunk_ids": {"$contains": "chunk_b_id"}},
    time_range="last_30d"
)
# Result: 234 conversations included this chunk
# Of those, 89% of users were NOT warranty customers

Step 4: Implement fix
─────────────────────────────────────
# Add customer-type metadata to retrieval filter
retrieval_filter = {
    "applicable_to": {
        "$in": [user.subscription_type, "all_customers"]
    }
}

Step 5: Validate fix
─────────────────────────────────────
# Re-run the same query through the fixed pipeline
# Verify chunk_b no longer appears for standard customers
# Run regression test on 50 refund-related queries
```

---

## Case Study 8: Cost Attribution Using Trace Metadata

### Implementation

```python
# Every AI call is tagged with attribution metadata
class CostAttributor:
    def tag_request(self, request, context):
        """Add cost attribution metadata to every AI request."""
        return {
            **request,
            "metadata": {
                # Who
                "user_id": context.user_id,
                "org_id": context.org_id,
                "user_tier": context.subscription_tier,  # free/pro/enterprise
                
                # What
                "feature": context.feature_name,          # "chat", "search", "summarize"
                "agent_name": context.agent_name,         # For multi-agent systems
                "tool_name": context.current_tool,        # If called from a tool
                
                # Why
                "trigger": context.trigger,               # "user_action", "scheduled", "webhook"
                "conversation_id": context.conversation_id,
                "turn_number": context.turn_number,
            }
        }

# Aggregation query for cost reports
COST_ATTRIBUTION_QUERY = """
SELECT 
    date_trunc('day', timestamp) as day,
    metadata->>'org_id' as organization,
    metadata->>'feature' as feature,
    metadata->>'user_tier' as tier,
    SUM(cost_usd) as total_cost,
    COUNT(*) as request_count,
    AVG(cost_usd) as avg_cost_per_request,
    SUM(tokens_total) as total_tokens
FROM ai_requests
WHERE timestamp > NOW() - INTERVAL '30 days'
GROUP BY 1, 2, 3, 4
ORDER BY total_cost DESC
"""
```

### Real Cost Attribution Report (Monthly)

```
Organization: Acme Corp (Enterprise tier)
Period: March 2024
Total AI Cost: $8,247

By Feature:
  Document Analysis:    $4,120 (49.9%)  — 12,400 requests, $0.33/req
  Customer Chat:        $2,890 (35.0%)  — 89,000 requests, $0.032/req  
  Email Drafting:       $847   (10.3%)  — 28,400 requests, $0.030/req
  Search:              $390   (4.7%)   — 156,000 requests, $0.0025/req

By User (top 5):
  user_4421:  $1,240  — Power user in legal dept (heavy doc analysis)
  user_8832:  $890    — Uses AI chat extensively
  user_1156:  $720    — Bulk document processing
  user_9944:  $680    — Research team
  user_3321:  $510    — Sales team (email drafts)

Cost vs Value:
  Feature           | Cost    | Revenue Attributed | ROI
  Doc Analysis      | $4,120  | $28,000 (time saved)| 6.8x
  Customer Chat     | $2,890  | $12,000 (tickets deflected) | 4.2x
  Email Drafting    | $847    | $3,200 (productivity) | 3.8x
```

---

## Case Study 9: Observability for Compliance (Banking & Healthcare)

### Audit Trail Requirements

```python
class ComplianceObservabilityLayer:
    """
    Meets requirements for:
    - SOC 2 Type II (audit trail)
    - HIPAA (PHI access logging) 
    - OCC/FDIC guidance on AI in banking
    """
    
    def log_ai_interaction(self, request, response, context):
        audit_record = {
            # Immutable record ID
            "audit_id": uuid4(),
            "timestamp": datetime.utcnow().isoformat(),
            
            # What was asked
            "input_hash": sha256(request.messages[-1]["content"]),  # Don't store PII in logs
            "input_classification": self.classify_sensitivity(request),
            "pii_detected": self.detect_pii_categories(request),
            
            # What model did
            "model_used": request.model,
            "model_version": response.model_version,  # Exact model version for reproducibility
            "temperature": request.temperature,
            "response_hash": sha256(response.content),
            
            # Guardrail decisions
            "guardrails_applied": self.get_guardrail_results(response),
            "content_filtered": response.was_filtered,
            "override_applied": context.get("human_override"),
            
            # Who and why
            "requesting_user": context.user_id,
            "user_role": context.user_role,
            "business_justification": context.get("justification"),
            "data_classification": context.data_classification,  # public/internal/confidential/restricted
            
            # Retention
            "retention_policy": "7_years",  # Regulatory requirement
            "deletion_eligible_date": datetime.utcnow() + timedelta(days=2555),
        }
        
        # Write to immutable audit log (append-only, tamper-evident)
        self.audit_log.append(audit_record)
        
        # If PHI/PII involved, additional logging
        if audit_record["pii_detected"]:
            self.phi_access_log.append({
                "audit_id": audit_record["audit_id"],
                "phi_categories": audit_record["pii_detected"],
                "access_purpose": context.get("purpose"),
                "minimum_necessary_applied": True,
            })
    
    def generate_compliance_report(self, period: str) -> dict:
        """Monthly compliance report for regulators."""
        return {
            "period": period,
            "total_ai_interactions": self.count_interactions(period),
            "interactions_with_pii": self.count_pii_interactions(period),
            "guardrail_activations": self.count_guardrail_triggers(period),
            "human_overrides": self.count_overrides(period),
            "model_versions_used": self.list_model_versions(period),
            "data_retention_compliance": self.verify_retention(period),
            "access_anomalies_detected": self.list_anomalies(period),
        }
```

### Healthcare-Specific Trace Example

```
Trace: clinical_note_summarization_audit_20240315_143022
Patient context: [REDACTED in trace, hash stored for lookup]
Clinician: Dr. Smith (Role: Attending, Department: Cardiology)

├── [PHI Detection] 12ms
│   ├── PHI found: patient_name, DOB, MRN, diagnosis_codes
│   ├── Action: PHI masked before sending to external model
│   └── Minimum necessary: Only relevant clinical section sent
│
├── [Model Call] model=gpt-4, provider=azure_openai_hipaa_endpoint
│   ├── Data residency: US-East (HIPAA-compliant Azure region)
│   ├── BAA in place: Yes (Microsoft BAA #2024-0142)
│   ├── Input tokens: 2,400 (de-identified)
│   └── Output tokens: 380
│
├── [Output Validation] 
│   ├── Clinical accuracy check: PASS (no contradictions with source)
│   ├── Hallucination check: PASS (all claims traceable to input)
│   ├── Disclaimer added: "AI-generated summary. Verify before clinical use."
│   └── Confidence: 0.91
│
└── [Audit Record Written]
    ├── Retained for: 7 years (HIPAA requirement)
    ├── Access logged in: PHI access audit trail
    └── Searchable by: audit_id, clinician_id, timestamp, department
```

---

## Case Study 10: Handling 10M Traces/Day Without Blowing Up Storage

**Problem:** At 10M AI traces/day, each averaging 2KB, that's 20GB/day raw = 600GB/month = $15K+/month in storage alone, plus query costs.

### Sampling Strategy

```python
class AdaptiveSampler:
    """
    Head-based sampling that keeps interesting traces and drops routine ones.
    Target: Store 5% of traces = 500K/day = 1GB/day
    """
    
    RULES = [
        # Always keep (100% sampling)
        {"condition": "error == true", "rate": 1.0, "reason": "debug errors"},
        {"condition": "cost_usd > 0.50", "rate": 1.0, "reason": "expensive requests"},
        {"condition": "latency_ms > 15000", "rate": 1.0, "reason": "slow requests"},
        {"condition": "user_feedback == 'negative'", "rate": 1.0, "reason": "quality issues"},
        {"condition": "guardrail_triggered == true", "rate": 1.0, "reason": "safety events"},
        {"condition": "is_new_user == true", "rate": 0.5, "reason": "onboarding experience"},
        
        # Sample moderately (20%)
        {"condition": "feature == 'chat' AND turn_number == 1", "rate": 0.2, "reason": "first messages"},
        {"condition": "model == 'gpt-4'", "rate": 0.2, "reason": "expensive model usage"},
        
        # Sample lightly (2%)
        {"condition": "cache_hit == true", "rate": 0.02, "reason": "cache hits are boring"},
        {"condition": "feature == 'autocomplete'", "rate": 0.01, "reason": "very high volume, low value"},
        
        # Default
        {"condition": "true", "rate": 0.05, "reason": "baseline 5% sample"},
    ]
    
    def should_sample(self, trace_attributes: dict) -> bool:
        for rule in self.RULES:
            if self.evaluate_condition(rule["condition"], trace_attributes):
                return random.random() < rule["rate"]
        return random.random() < 0.05
```

### Retention Policies

```yaml
# Tiered retention to manage storage costs
retention_policies:
  hot_tier:  # Fast SSD, instant queries
    duration: 7_days
    storage: "Tempo hot storage"
    cost: "$0.10/GB/day"
    data: "all sampled traces (full detail)"
    
  warm_tier:  # Standard storage, <5s query time
    duration: 30_days
    storage: "S3 + Tempo compacted blocks"
    cost: "$0.023/GB/month"
    data: "sampled traces (metadata + first/last spans only)"
    
  cold_tier:  # Archive, minutes to query
    duration: 365_days
    storage: "S3 Glacier Instant Retrieval"
    cost: "$0.004/GB/month"
    data: "aggregated metrics only (no individual trace details)"
    exceptions: "compliance-tagged traces kept in full for 7 years"

# Storage math:
#   Hot:  1GB/day × 7 days × $0.10 = $0.70/day
#   Warm: 0.3GB/day × 30 days × $0.023/30 = $0.007/day  
#   Cold: 0.05GB/day × 365 × $0.004/30 = $0.024/day
#   Total: ~$25/day = $750/month (vs $15K/month storing everything)
```

### Aggregation Before Storage

```python
class TraceAggregator:
    """Compute and store metrics without keeping raw trace data."""
    
    def aggregate_hourly(self, traces_batch: list):
        """Run every hour on the raw trace stream."""
        metrics = {
            "timestamp": current_hour(),
            "request_count": len(traces_batch),
            "by_model": defaultdict(lambda: {"count": 0, "cost": 0, "latency_sum": 0}),
            "by_feature": defaultdict(lambda: {"count": 0, "cost": 0, "errors": 0}),
            "latency_histogram": [],  # Pre-computed percentiles
            "quality_scores": {
                "groundedness_avg": 0,
                "hallucination_count": 0,
                "user_satisfaction_avg": 0,
            },
            "error_counts_by_type": defaultdict(int),
        }
        
        for trace in traces_batch:
            model = trace["model"]
            metrics["by_model"][model]["count"] += 1
            metrics["by_model"][model]["cost"] += trace["cost_usd"]
            metrics["by_model"][model]["latency_sum"] += trace["latency_ms"]
            # ... aggregate all dimensions
        
        # Store only the aggregate (80 bytes vs 2KB per trace)
        self.metrics_store.write(metrics)
```

---

## Case Study 11: Custom AI-Specific Metrics

### Groundedness Over Time

```python
class GroundednessTracker:
    """Track how well AI responses are grounded in retrieved context."""
    
    def compute_groundedness(self, response: str, context_chunks: list) -> float:
        """
        Score 0-1: What fraction of claims in the response are 
        supported by the provided context?
        """
        claims = self.extract_claims(response)  # NLI-based claim extraction
        
        supported = 0
        for claim in claims:
            for chunk in context_chunks:
                if self.entailment_score(chunk, claim) > 0.8:
                    supported += 1
                    break
        
        return supported / len(claims) if claims else 1.0
    
    def track(self, trace_id: str, response: str, chunks: list, metadata: dict):
        score = self.compute_groundedness(response, chunks)
        
        # Emit as metric
        self.prometheus.histogram(
            "ai_groundedness_score",
            score,
            labels={
                "feature": metadata["feature"],
                "model": metadata["model"],
                "collection": metadata["retrieval_collection"],
            }
        )
        
        # Attach to trace
        self.langfuse.score(trace_id, "groundedness", score)
        
        # Alert if below threshold
        if score < 0.6:
            self.alert_queue.push({
                "type": "low_groundedness",
                "trace_id": trace_id,
                "score": score,
                "metadata": metadata,
            })
```

### Hallucination Rate by Category

```python
# Track hallucination patterns to identify systemic issues
HALLUCINATION_CATEGORIES = {
    "fabricated_fact": "Model stated something not in context or reality",
    "wrong_attribution": "Correct fact attributed to wrong source",
    "temporal_confusion": "Mixed up dates, versions, or timelines",
    "entity_confusion": "Confused similar entities (products, people, companies)",
    "extrapolation": "Drew conclusions not supported by evidence",
    "stale_information": "Used outdated information despite newer context",
}

class HallucinationTracker:
    def record_hallucination(self, trace_id: str, category: str, details: dict):
        self.prometheus.counter(
            "ai_hallucinations_total",
            labels={
                "category": category,
                "feature": details["feature"],
                "model": details["model"],
            }
        ).inc()
        
    def weekly_report(self) -> dict:
        """Generate weekly hallucination analysis."""
        return {
            "total_evaluated": 12400,
            "total_hallucinations": 186,
            "rate": "1.5%",
            "by_category": {
                "fabricated_fact": 52,       # 28% — most common
                "temporal_confusion": 41,    # 22% — date-related issues
                "entity_confusion": 38,      # 20% — similar product names
                "extrapolation": 28,         # 15%
                "wrong_attribution": 18,     # 10%
                "stale_information": 9,      # 5%
            },
            "trending_up": ["temporal_confusion"],  # Getting worse
            "trending_down": ["fabricated_fact"],   # Improving
            "action_items": [
                "Temporal confusion increasing — add date metadata to chunks",
                "Entity confusion high for 'Pro' vs 'Pro Max' products — add disambiguation",
            ]
        }
```

### Tool Success Rate Trends

```python
# For agentic systems: track which tools succeed/fail over time
class ToolMetrics:
    def record_tool_call(self, tool_name: str, result: ToolResult, context: dict):
        labels = {"tool": tool_name, "agent": context["agent_name"]}
        
        self.prometheus.counter("tool_calls_total", labels=labels).inc()
        
        if result.success:
            self.prometheus.counter("tool_calls_success_total", labels=labels).inc()
        else:
            self.prometheus.counter("tool_calls_failed_total", labels={
                **labels, "error_type": result.error_type
            }).inc()
        
        self.prometheus.histogram(
            "tool_call_duration_seconds",
            result.duration_seconds,
            labels=labels
        )
    
    def get_tool_health_report(self) -> dict:
        """
        Real output example:
        
        Tool Health (Last 24h):
          web_search:     94.2% success, p95=2.1s, 12,400 calls
          database_query: 99.1% success, p95=0.3s,  8,900 calls
          calculator:     99.9% success, p95=0.01s, 3,200 calls
          email_send:     97.8% success, p95=1.4s,  1,100 calls
          file_read:      88.4% success, p95=0.8s,    640 calls  ← DEGRADED
          
        file_read degradation analysis:
          - 73 failures in last 24h (vs baseline of 12)
          - Error types: permission_denied (41), not_found (22), timeout (10)
          - Correlated with: deployment v2.4.1 changed file path resolution
        """
        pass
```

---

## Key Takeaways

1. **Traces are your source of truth.** When users report bad answers, the trace shows exactly what went wrong — bad retrieval, wrong model choice, or corrupted data.

2. **Four dashboards cover all stakeholders:** Ops (uptime), Quality (correctness), Cost (budget), UX (user happiness). Build all four from day one.

3. **Alert on leading indicators:** Retrieval score drop predicts quality drop. Token count spike predicts cost spike. Catch problems before users notice.

4. **Compliance observability is non-negotiable** in regulated industries. Design your trace schema for auditability from the start — retrofitting is painful.

5. **Sampling is essential at scale.** Keep 100% of interesting traces (errors, expensive, slow) and sample routine traffic at 2-5%.

6. **Cost attribution enables accountability.** When teams see their AI costs per feature, they optimize naturally.

7. **Custom AI metrics (groundedness, hallucination rate, tool success) are more valuable than generic infrastructure metrics** for AI-specific debugging.
