# Runbook Library for AI Systems

## What is a Runbook?

A runbook is a **step-by-step procedure** for handling a specific type of incident. It removes guesswork from incident response — when an alert fires at 3 AM, you follow the runbook instead of trying to think clearly while half-asleep.

---

## Why AI Systems Need Specialized Runbooks

Traditional runbooks cover: restart service, scale up, failover database, clear disk space.

AI systems need runbooks for:
- "Quality dropped but nothing is technically broken"
- "Model is hallucinating more than usual"
- "We're spending 3x normal and don't know why"
- "Provider is slow but not down"
- "Users are getting wrong answers from stale data"

These aren't traditional infrastructure problems — they require AI-specific diagnosis and remediation.

---

## Runbook Template

```markdown
# Runbook: [Incident Type]

## Metadata
- **Severity**: P0/P1/P2/P3
- **Trigger**: What alert fires this runbook
- **Owner**: Team/person responsible for maintaining this runbook
- **Last reviewed**: [Date]
- **Estimated resolution time**: [Duration]

## First Response (< 5 minutes)
1. Verify the alert is real (not a false positive)
2. Check scope of impact (how many users affected?)
3. Communicate: post in incident channel

## Diagnosis (< 15 minutes)
- Check A: [specific check with commands/links]
- Check B: [specific check]
- Decision tree: if A then X, if B then Y

## Mitigation (immediate, reduce blast radius)
- Action 1: [immediate action to reduce user impact]
- Action 2: [contain the problem]

## Resolution (fix root cause)
- Fix 1: [permanent fix steps]
- Verification: [how to confirm it's fixed]

## Post-Incident
- [ ] Update incident channel with resolution
- [ ] Write post-incident review
- [ ] Update this runbook if needed
- [ ] Create tickets for follow-up improvements
```

---

## Runbook 1: Provider Outage

```markdown
# Runbook: Provider Outage

## Metadata
- **Severity**: P1
- **Trigger**: Alert `provider_error_rate > 5% for 2 minutes`
- **Owner**: Platform team
- **Last reviewed**: 2024-12-01
- **Estimated resolution time**: 5-60 minutes (depends on provider)

## First Response (< 5 minutes)

1. **Verify the outage is real**:
   - Check provider status page: https://status.openai.com
   - Run manual health check: `curl -X POST https://api.openai.com/v1/chat/completions ...`
   - Check if it's just rate limiting (429) vs actual outage (500/503)
   
2. **Check if failover already activated**:
   - Dashboard: [link to failover dashboard]
   - If auto-failover fired → verify it's working, skip to monitoring
   - If auto-failover did NOT fire → trigger manual failover

3. **Communicate**:
   - Post in #incidents: "Investigating provider outage, failover [active/activating]"

## Diagnosis (< 5 minutes for outage, failover first)

- **Is it affecting all models or specific ones?**
  - Check: GPT-4 health, GPT-3.5 health, embeddings health
  - If only one model: route to alternative model, not full failover

- **Is it regional?**
  - Check: US endpoint vs EU endpoint
  - If regional: route to healthy region

- **Is it our quota/auth or provider-wide?**
  - Check provider status page
  - Check our API key status
  - If auth issue: rotate keys, check billing

## Mitigation (< 5 minutes)

1. **Trigger failover** (if not automatic):
   ```bash
   # Manual failover command
   kubectl set env deployment/ai-gateway PRIMARY_PROVIDER=azure-openai
   # OR
   curl -X POST https://internal-api/admin/failover \
     -d '{"from": "openai", "to": "azure-openai"}'
   ```

2. **Verify failover is healthy**:
   - Check response quality from secondary provider
   - Verify latency is acceptable (may be higher)
   - Monitor error rate (should drop to < 1%)

3. **Communicate**: "Failover active, service restored on secondary provider. Monitoring quality."

## Resolution

1. **Monitor primary provider recovery**:
   - Set up health check polling every 60 seconds
   - Wait for 5 consecutive successful checks before considering recovered

2. **Gradual traffic shift back** (when primary recovers):
   ```
   Step 1: Route 10% traffic to primary, wait 5 min, verify
   Step 2: Route 50% traffic to primary, wait 5 min, verify
   Step 3: Route 100% traffic to primary
   ```

3. **Verify quality**: compare eval scores between providers during transition

## Post-Incident
- [ ] Duration of outage: ___
- [ ] Failover time: ___
- [ ] User impact during failover: ___
- [ ] Quality difference on secondary provider: ___
- [ ] Update status page
- [ ] Write post-incident review
- [ ] Action items: improve failover speed? Add another provider?
```

---

## Runbook 2: Hallucination Spike

```markdown
# Runbook: Hallucination Spike

## Metadata
- **Severity**: P1
- **Trigger**: Alert `hallucination_rate > 8% for 10 minutes`
- **Owner**: AI Quality team
- **Last reviewed**: 2024-12-01
- **Estimated resolution time**: 30-120 minutes

## First Response (< 5 minutes)

1. **Verify the spike is real**:
   - Check sample size (is this statistically significant?)
   - Minimum: 50+ evaluated responses in the window
   - Review 3-5 flagged responses manually — are they actually hallucinations?

2. **Immediately tighten guardrails**:
   ```bash
   # Lower confidence threshold (blocks more but may over-block)
   curl -X POST https://internal-api/admin/guardrails \
     -d '{"confidence_threshold": 0.7, "reason": "hallucination_spike"}'
   ```

3. **Communicate**: "Investigating hallucination spike. Guardrails tightened."

## Diagnosis (< 15 minutes)

### Check A: Retrieval Quality
- Run test queries against vector DB
- Compare retrieved results to expected documents
- Check: are wrong documents being retrieved?
- If YES → vector DB issue, see Runbook: Vector DB Degradation

### Check B: Context Construction
- Check recent prompt/context template changes
- Review: is relevant context being included in prompts?
- Check token count: is context being truncated?
- If TRUNCATION → context window overflow, increase limit or compress

### Check C: Model Behavior
- Test with known queries that should produce grounded responses
- Compare outputs to last known good state
- Check: did provider update the model?
- If MODEL CHANGED → pin to previous version or switch provider

### Check D: Data Quality
- Check data pipeline status: any recent ingestion failures?
- Sample vector DB for recently ingested documents
- Check: is there corrupted or incorrect data?
- If DATA ISSUE → identify and remove bad data, re-embed

## Mitigation (while diagnosing)

1. **Enable strict mode**: only serve responses with > 0.8 confidence
2. **Add disclaimers**: flag responses with lower confidence to users
3. **Increase retrieval count**: retrieve more documents for cross-reference
4. **Enable response validation**: cross-check claims against source

## Resolution (based on diagnosis)

### If retrieval issue:
1. Check vector DB cluster health
2. Rebuild index if fragmented
3. Verify embeddings are using correct model
4. Re-run quality tests

### If context truncation:
1. Reduce retrieval count or chunk size
2. Implement context prioritization (most relevant first)
3. Consider model with larger context window

### If model change:
1. Pin to specific model version
2. Or switch to secondary provider
3. Re-run eval suite against new model
4. Decide: adapt prompts or reject model update

### If data quality:
1. Identify bad data source/batch
2. Remove from vector DB
3. Re-ingest from clean source
4. Add data validation to ingestion pipeline

## Verification

1. Run full eval suite: hallucination rate should be < 5%
2. Monitor for 1 hour after fix
3. Gradually relax guardrails back to normal thresholds
4. Confirm metrics stable for 4 hours

## Post-Incident
- [ ] Root cause identified: ___
- [ ] Hallucination rate peak: ___%
- [ ] User impact (approximate responses affected): ___
- [ ] Time to detection: ___
- [ ] Time to mitigation: ___
- [ ] Time to resolution: ___
- [ ] Guardrails relaxed back to normal: [ ] yes [ ] not yet
```

---

## Runbook 3: Cost Runaway

```markdown
# Runbook: Cost Runaway

## Metadata
- **Severity**: P2
- **Trigger**: Alert `hourly_cost > 3x rolling_7d_average`
- **Owner**: Platform team
- **Last reviewed**: 2024-12-01
- **Estimated resolution time**: 15-60 minutes

## First Response (< 5 minutes)

1. **Identify the source**:
   - Check cost dashboard: which endpoint/feature/user is spending?
   - Top consumers in last hour vs normal
   - Any single request > $5?

2. **Quick assessment**:
   - Is this a single runaway agent? → Kill it immediately
   - Is this a traffic spike? → Normal scaling, monitor budget
   - Is this cache failure? → All requests hitting model, fix cache
   - Is this abuse? → Rate limit the user

3. **If runaway agent detected**:
   ```bash
   # Kill specific agent
   curl -X POST https://internal-api/admin/agents/kill \
     -d '{"agent_id": "<id>", "reason": "cost_runaway"}'
   ```

## Diagnosis (< 10 minutes)

### Check A: Single User/Agent
- Query: top 10 users by cost in last hour
- If single user > 50% of spend → investigate that user
- Check: is it a loop? (same request pattern repeated)

### Check B: Cache Health
- Check cache hit rate: if < 10% → cache is broken
- Check: Redis connectivity, memory, evictions
- If cache down → requests hitting model directly (expensive)

### Check C: Traffic Spike
- Compare request count to normal
- If requests normal but cost high → token usage per request increased
- Check: was a prompt changed? New feature enabled? Context size increased?

### Check D: Retry Storm
- Check retry rate: are failed requests being retried excessively?
- If retries > 3x normal → something is failing and being retried

## Mitigation

### If agent loop:
1. Kill the agent
2. Enable agent iteration limits if not already set
3. Set per-agent token budget

### If cache failure:
1. Fix cache (restart Redis, fix connection)
2. Enable request coalescing (deduplicate identical requests)
3. Temporarily enable aggressive client-side caching

### If traffic spike:
1. Enable rate limiting at gateway level
2. Prioritize paying/premium users
3. Queue low-priority requests
4. If budget will be exhausted: enable degraded mode (shorter responses)

### If retry storm:
1. Identify what's failing
2. Implement exponential backoff if not present
3. Set max retry limit
4. Fix underlying failure

## Resolution

1. Root cause identified and fixed
2. Remove temporary mitigations (rate limits, degraded mode)
3. Calculate total unexpected spend: $___
4. Implement prevention:
   - Per-agent token budgets
   - Per-user hourly cost limits
   - Cache failure circuit breaker
   - Retry budget limits

## Post-Incident
- [ ] Total unexpected cost: $___
- [ ] Root cause: ___
- [ ] Duration of elevated spending: ___
- [ ] Prevention measures implemented: ___
```

---

## Runbook 4: Quality Degradation

```markdown
# Runbook: Quality Degradation

## Metadata
- **Severity**: P2
- **Trigger**: Alert `faithfulness_score avg < 0.85 for 15 minutes`
- **Owner**: AI Quality team
- **Last reviewed**: 2024-12-01
- **Estimated resolution time**: 30-180 minutes

## First Response (< 10 minutes)

1. **Verify degradation**:
   - Check eval dashboard: is this a trend or a blip?
   - Sample 5-10 recent responses manually — confirm quality issue
   - Check: is this all queries or specific types?

2. **Assess severity**:
   - Score dropped from 0.92 to 0.88 → watch closely, not emergency
   - Score dropped from 0.92 to 0.75 → significant, investigate immediately
   - Score dropped from 0.92 to 0.50 → critical, activate P1 response

3. **Communicate**: "Quality degradation detected, investigating. Current score: X (baseline: Y)"

## Diagnosis

### Check A: Recent Deployments
- Any deployments in last 24 hours? (prompt changes, config changes)
- If YES → compare quality before and after deployment
- If deployment caused it → rollback

### Check B: Provider Model Changes
- Check provider changelog/status
- Run same eval queries against model directly (without our system)
- If model behavior changed → provider updated weights
- Action: pin version or switch provider

### Check C: Data Freshness
- When was vector DB last updated?
- Are we serving stale information?
- Run freshness check on key documents
- If STALE → trigger re-ingestion, this is likely the cause

### Check D: Input Distribution Shift
- Are users asking different types of questions?
- Compare this week's query distribution to last month
- If SHIFT → prompts/retrieval may need updating for new patterns

### Check E: Retrieval Quality
- Run retrieval accuracy test (known queries → expected documents)
- Check recall@10 score
- If RETRIEVAL DEGRADED → investigate vector DB (see Vector DB runbook)

## Resolution (based on diagnosis)

### If deployment caused it:
```bash
# Rollback to previous version
kubectl rollout undo deployment/ai-service
# OR rollback prompt version
curl -X POST https://internal-api/admin/prompts/rollback \
  -d '{"version": "previous"}'
```

### If provider model changed:
1. Pin to specific model version (if available)
2. Adjust prompts for new model behavior
3. Or failover to secondary provider
4. Run full eval suite to assess impact

### If data stale:
1. Trigger manual re-ingestion pipeline
2. Verify pipeline health for future runs
3. Add freshness alerting if not present

### If input distribution shift:
1. Analyze new query types
2. Update retrieval strategy for new patterns
3. Add few-shot examples for new query types
4. Consider fine-tuning or prompt updates

## Verification
1. Re-run eval suite → score should be > 0.90
2. Monitor for 4 hours
3. Check user feedback metrics (thumbs up/down)
4. Confirm resolution in incident channel
```

---

## Runbook 5: Vector DB Latency

```markdown
# Runbook: Vector DB Latency Spike

## Metadata
- **Severity**: P2
- **Trigger**: Alert `vector_search_p95 > 500ms for 5 minutes`
- **Owner**: Platform team
- **Last reviewed**: 2024-12-01
- **Estimated resolution time**: 15-60 minutes

## First Response (< 5 minutes)

1. **Check cluster health**:
   - All nodes up? Any node showing degraded?
   - Memory utilization per node
   - CPU utilization per node
   - Network connectivity between nodes

2. **Check if it's impacting users**:
   - End-to-end response latency increase?
   - If vector DB is slow but E2E is fine → cache is absorbing it, less urgent

3. **Communicate**: "Vector DB latency elevated, investigating. E2E impact: [yes/no]"

## Diagnosis

### Check A: Node Health
```bash
# Check cluster status (example for Qdrant/Pinecone/Weaviate)
curl http://vector-db:6333/cluster/status
```
- Any nodes unhealthy? → Restart or replace
- Any nodes at 100% memory? → Scale out

### Check B: Memory Pressure
- Index size vs available memory
- If index > memory → spilling to disk (very slow)
- Action: add nodes or reduce index size

### Check C: Query Pattern Change
- Are queries suddenly more complex? (more vectors, longer filters)
- High fan-out queries consuming resources?
- Bulk ingestion running at same time as queries?

### Check D: Index Fragmentation
- Many updates/deletes fragmenting the index?
- Last index optimization: when?
- If fragmented → schedule off-peak rebuild

## Mitigation

1. **Add read replicas** (if possible):
   ```bash
   # Scale replica count
   kubectl scale statefulset vector-db --replicas=5
   ```

2. **Reduce query load**:
   - Increase cache TTL for vector results
   - Reduce top_k (retrieve fewer results)
   - Enable query result caching

3. **If bulk ingestion is the cause**:
   - Pause ingestion pipeline
   - Schedule for off-peak hours
   - Implement write throttling

## Resolution

1. Root cause addressed (scaled, restarted, rebuilt index)
2. P95 latency back below 200ms
3. Remove temporary mitigations
4. Add capacity if underlying cause is growth

## Post-Incident
- [ ] Root cause: ___
- [ ] Peak latency: ___ms
- [ ] Duration: ___
- [ ] User impact (E2E latency increase): ___
- [ ] Capacity action needed: ___
```

---

## Runbook Automation Levels

### Level 1: Fully Automated (No Human)

```
Appropriate for:
- Provider failover (when secondary is proven equivalent)
- Cache reconstruction (no risk)
- Auto-scaling (within limits)
- Agent kill (when budget exceeded)

Implementation:
- Alert fires → automation runs → notification sent
- Human reviews after the fact
- Automatic rollback if automation makes things worse
```

### Level 2: Semi-Automated (Human Approves)

```
Appropriate for:
- Model rollback (quality judgment needed)
- Rate limiting users (business impact)
- Guardrail threshold changes (balance safety vs usability)
- Provider switching (quality comparison needed)

Implementation:
- Alert fires → automation proposes action → human approves → executes
- Timeout: if no response in 10 min, execute anyway for P1
```

### Level 3: Manual (Human Executes)

```
Appropriate for:
- Data quality investigation (judgment heavy)
- Prompt changes (creative decision)
- Architecture changes (complex reasoning)
- Security incidents (forensics needed)

Implementation:
- Alert fires → runbook provides steps → human follows steps
- Checklist ensures nothing is missed
- Decision trees guide through ambiguous situations
```

---

## Keeping Runbooks Current

### After Every Incident
- Did the runbook help? What was missing?
- Were any steps wrong or outdated?
- Add the scenario if not covered
- Update commands/links if changed

### Quarterly Audit
```markdown
## Runbook Audit Checklist

For each runbook:
- [ ] Last used: [date] (if > 6 months, consider removal or gameday)
- [ ] All links/commands still work
- [ ] Escalation contacts current
- [ ] Thresholds still appropriate
- [ ] Automation still functioning
- [ ] Reviewed by someone other than author
```

### Gameday Testing
- Once per quarter: pick a runbook, simulate the incident, execute the runbook
- Time the response: are steps achievable in stated time?
- Find gaps: anything assumed but not documented?

---

## Key Takeaways

1. **Runbooks save lives (and SLOs)** — you can't think clearly at 3 AM
2. **AI runbooks need quality diagnosis** — not just "restart the service"
3. **Automate what's safe, guide what's complex** — use the right automation level
4. **Test your runbooks** — an untested runbook is just documentation
5. **Update after every use** — runbooks are living documents
6. **Include decision trees** — AI incidents often have multiple possible causes
