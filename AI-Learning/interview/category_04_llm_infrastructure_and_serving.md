# LLM Serving Infrastructure - Staff Architect Interview

## Question 31: LLM Inference Optimization at Scale
**Difficulty: Staff Level | Topic: ML Systems | Asked at: OpenAI, Anthropic, Google DeepMind**

You need to serve a 70B parameter LLM with sub-2-second time-to-first-token and 50+ tokens/second throughput for 10,000 concurrent users. Design the serving architecture including model parallelism, batching strategies, and KV cache management.

### Expected Answer:

**Production LLM Serving Architecture:**

1. **Model Parallelism Strategy for 70B Parameters:**
   ```
   70B params × 2 bytes (FP16) = 140GB model weights
   + KV cache + activations = ~200GB total memory needed
   
   Option A: Tensor Parallelism (TP=8 across 8 GPUs on 1 node)
   ┌──────────────────────────────────────────┐
   │  Single Node: 8× A100 80GB (640GB total) │
   │  Each GPU: 140GB/8 = 17.5GB weights      │
   │  Remaining: 62.5GB for KV cache per GPU   │
   │  All-reduce between GPUs (NVLink: 600GB/s)│
   └──────────────────────────────────────────┘
   
   Option B: Pipeline Parallelism (PP=2 nodes × TP=4)
   ┌─────────────┐    ┌─────────────┐
   │ Node 1: L0-39│───▶│ Node 2: L40-79│
   │ TP=4 GPUs   │    │ TP=4 GPUs    │
   └─────────────┘    └──────────────┘
   - Higher latency (inter-node communication)
   - But allows larger batch sizes
   ```

2. **Continuous Batching (Iteration-Level Scheduling):**
   ```python
   class ContinuousBatcher:
       """
       Key insight: Don't wait for all sequences in a batch to finish.
       Insert new requests as soon as any sequence completes.
       """
       def __init__(self, max_batch_size=256, max_tokens_per_step=4096):
           self.running_sequences = []  # Currently generating
           self.waiting_queue = PriorityQueue()  # Pending requests
           self.max_batch = max_batch_size
       
       def iteration_step(self):
           # Remove completed sequences
           completed = [s for s in self.running_sequences if s.is_done()]
           for seq in completed:
               self.running_sequences.remove(seq)
               seq.callback(seq.output)
           
           # Fill empty slots with new requests
           available_slots = self.max_batch - len(self.running_sequences)
           available_memory = self.get_free_kv_cache_blocks()
           
           while available_slots > 0 and not self.waiting_queue.empty():
               next_req = self.waiting_queue.peek()
               blocks_needed = self.estimate_blocks(next_req)
               
               if blocks_needed <= available_memory:
                   self.waiting_queue.get()
                   self.running_sequences.append(next_req)
                   available_slots -= 1
                   available_memory -= blocks_needed
               else:
                   break  # No memory for more sequences
           
           # Run one forward pass for all running sequences
           self.model_forward(self.running_sequences)
   ```

3. **PagedAttention KV Cache Management:**
   ```python
   class PagedKVCacheManager:
       """
       Inspired by OS virtual memory: KV cache stored in non-contiguous blocks.
       Eliminates memory fragmentation that wastes 60-80% of GPU memory.
       """
       def __init__(self, num_blocks=10000, block_size=16, num_layers=80):
           # Each block stores KV for 16 tokens across all layers
           self.block_size = block_size  # tokens per block
           self.free_blocks = list(range(num_blocks))
           self.block_tables = {}  # sequence_id -> [block_ids]
       
       def allocate(self, sequence_id, num_tokens):
           blocks_needed = ceil(num_tokens / self.block_size)
           if len(self.free_blocks) < blocks_needed:
               # Trigger preemption of lowest-priority sequence
               self.preempt_sequence()
           
           allocated = [self.free_blocks.pop() for _ in range(blocks_needed)]
           self.block_tables[sequence_id] = allocated
           return allocated
       
       def append_token(self, sequence_id):
           """Called after each generated token."""
           current_blocks = self.block_tables[sequence_id]
           last_block_usage = self.get_block_usage(current_blocks[-1])
           
           if last_block_usage >= self.block_size:
               # Need a new block
               new_block = self.free_blocks.pop()
               current_blocks.append(new_block)
       
       def fork(self, parent_seq_id, child_seq_id):
           """Copy-on-write for beam search / parallel sampling."""
           # Share blocks, only copy when modified
           self.block_tables[child_seq_id] = self.block_tables[parent_seq_id].copy()
           self.increment_ref_counts(self.block_tables[parent_seq_id])
   ```

4. **Speculative Decoding for Latency Reduction:**
   ```python
   class SpeculativeDecoder:
       """
       Use small draft model to generate K candidate tokens,
       then verify all K tokens in single forward pass of large model.
       Achieves 2-3x speedup without quality loss.
       """
       def __init__(self, target_model_70B, draft_model_7B, k=5):
           self.target = target_model_70B
           self.draft = draft_model_7B
           self.k = k  # speculation length
       
       def generate_token(self, context):
           # Draft model generates K tokens (fast, cheap)
           draft_tokens = []
           draft_probs = []
           for _ in range(self.k):
               token, prob = self.draft.sample(context)
               draft_tokens.append(token)
               draft_probs.append(prob)
               context = context + [token]
           
           # Target model verifies all K tokens in one forward pass
           target_probs = self.target.forward(context_with_drafts)
           
           # Accept tokens where target agrees with draft
           accepted = 0
           for i in range(self.k):
               acceptance_prob = min(1, target_probs[i] / draft_probs[i])
               if random() < acceptance_prob:
                   accepted += 1
               else:
                   # Resample from adjusted distribution
                   return accepted + 1  # tokens generated this iteration
           
           return self.k + 1  # All accepted + bonus token
   ```

5. **Capacity Planning for 10K Concurrent Users:**
   ```
   Assumptions:
   - Avg input: 500 tokens, Avg output: 200 tokens
   - Target: 50 tokens/sec throughput per user
   - Time-to-first-token: < 2 seconds
   
   Per-GPU throughput (A100, TP=8 on one node):
   - Batch size 64: ~3200 tokens/sec aggregate
   - Per user: 3200/64 = 50 tokens/sec ✓
   
   For 10K concurrent users:
   - Need: 10000/64 = 156 serving instances
   - Each instance: 8× A100 = 1 node
   - Total: 156 nodes × 8 GPUs = 1,248 A100 GPUs
   
   With speculative decoding (2.5x speedup):
   - 156/2.5 = ~63 nodes needed
   - Total: 504 A100 GPUs
   
   Cost optimization:
   - Peak hours (8hr): 63 nodes on-demand
   - Off-peak (16hr): 20 nodes + queue
   - Monthly cost: ~$2M (cloud) or $500K (owned, amortized)
   ```

---

## Question 32: Model Quantization for Production Deployment
**Difficulty: Staff Level | Topic: ML Optimization | Asked at: Meta, NVIDIA, Apple**

Compare GPTQ, AWQ, GGUF, and FP8 quantization for deploying LLMs in production. How do you measure quality degradation? Design a quantization pipeline that maintains <1% accuracy loss while achieving 4x memory reduction.

### Expected Answer:

**Quantization Techniques Comparison:**

1. **Technique Deep Dive:**

   | Method | Bits | Memory Savings | Quality Loss | Speed | Hardware |
   |--------|------|----------------|--------------|-------|----------|
   | FP16 (baseline) | 16 | 2x vs FP32 | 0% | 1x | Any GPU |
   | FP8 (E4M3) | 8 | 4x vs FP32 | <0.5% | 1.5x | H100, Ada |
   | GPTQ | 4 | 8x vs FP32 | 1-2% | 1.8x | Any GPU |
   | AWQ | 4 | 8x vs FP32 | 0.5-1% | 2x | Any GPU |
   | GGUF Q4_K_M | 4.5 | 7x vs FP32 | 1-3% | CPU-friendly | CPU/GPU |
   | 1-bit (BitNet) | 1.58 | 20x vs FP32 | 5-10% | 3x (specialized) | Custom |

2. **AWQ (Activation-Aware Weight Quantization):**
   ```python
   class AWQuantizer:
       """
       Key insight: Not all weights are equally important.
       Protect salient weights (those with large activation magnitudes).
       """
       def quantize_layer(self, weight, activations, group_size=128):
           # Step 1: Compute per-channel activation magnitudes
           activation_scale = activations.abs().mean(dim=0)
           
           # Step 2: Identify salient channels (top 1%)
           threshold = activation_scale.quantile(0.99)
           salient_mask = activation_scale > threshold
           
           # Step 3: Scale salient channels before quantization
           # This preserves precision for important weights
           scale_factor = torch.ones_like(activation_scale)
           scale_factor[salient_mask] = (activation_scale[salient_mask] / 
                                         activation_scale.mean())
           
           scaled_weight = weight * scale_factor.unsqueeze(0)
           
           # Step 4: Group quantization (per group_size channels)
           quantized = self.group_quantize(scaled_weight, 
                                           bits=4, 
                                           group_size=group_size)
           
           # Step 5: Store scale factors for dequantization
           return quantized, scale_factor
       
       def group_quantize(self, tensor, bits=4, group_size=128):
           """Quantize in groups for better precision."""
           n_groups = tensor.shape[1] // group_size
           quantized_groups = []
           scales = []
           zeros = []
           
           for g in range(n_groups):
               group = tensor[:, g*group_size:(g+1)*group_size]
               max_val = group.abs().max()
               scale = max_val / (2**(bits-1) - 1)
               zero_point = 0  # Symmetric quantization
               
               q_group = torch.round(group / scale).clamp(
                   -(2**(bits-1)), 2**(bits-1) - 1
               ).to(torch.int8)
               
               quantized_groups.append(q_group)
               scales.append(scale)
           
           return quantized_groups, scales
   ```

3. **Quality Evaluation Pipeline:**
   ```python
   class QuantizationQualityPipeline:
       def __init__(self, base_model, quantized_model):
           self.base = base_model
           self.quantized = quantized_model
       
       def evaluate(self):
           results = {}
           
           # 1. Perplexity on held-out data (most important)
           results['perplexity_base'] = self.compute_perplexity(self.base, 'wikitext')
           results['perplexity_quant'] = self.compute_perplexity(self.quantized, 'wikitext')
           results['perplexity_degradation'] = (
               results['perplexity_quant'] / results['perplexity_base'] - 1
           ) * 100  # Target: < 1%
           
           # 2. Task-specific benchmarks
           results['mmlu_base'] = self.eval_mmlu(self.base)
           results['mmlu_quant'] = self.eval_mmlu(self.quantized)
           
           # 3. Output distribution divergence
           results['kl_divergence'] = self.compute_kl_divergence(
               self.base, self.quantized, test_prompts
           )
           
           # 4. Long-context degradation (quantization errors accumulate)
           for ctx_len in [1024, 4096, 16384, 32768]:
               results[f'ppl_{ctx_len}'] = self.compute_perplexity(
                   self.quantized, context_length=ctx_len
               )
           
           # 5. Edge case detection
           results['failure_cases'] = self.find_failure_cases(
               self.base, self.quantized, test_prompts=10000
           )
           
           return results
       
       def compute_kl_divergence(self, model_a, model_b, prompts):
           """Measure how much output distributions differ."""
           total_kl = 0
           for prompt in prompts:
               logits_a = model_a.get_logits(prompt)
               logits_b = model_b.get_logits(prompt)
               probs_a = softmax(logits_a)
               probs_b = softmax(logits_b)
               total_kl += kl_divergence(probs_a, probs_b)
           return total_kl / len(prompts)
   ```

4. **Production Quantization Pipeline:**
   ```
   ┌─────────────┐    ┌──────────────┐    ┌─────────────┐
   │ Calibration  │───▶│ Quantize     │───▶│ Validate    │
   │ Dataset      │    │ (AWQ/GPTQ)   │    │ Quality     │
   │ 512 samples  │    │              │    │ < 1% loss?  │
   └─────────────┘    └──────────────┘    └──────┬──────┘
                                                  │
                                          Yes ──┐ │ ── No
                                                │ │
                                                ▼ ▼
                                    ┌──────────────────────┐
                                    │ Adjust: increase     │
                                    │ group_size, use mixed│
                                    │ precision for bad    │
                                    │ layers               │
                                    └──────────────────────┘
   ```

5. **Mixed-Precision Strategy:**
   - First/last layers: FP16 (most sensitive to quantization)
   - Attention QKV projections: INT8 (moderate sensitivity)
   - FFN layers: INT4 (most parameters, least sensitive)
   - Embeddings: INT8 (large but tolerant)
   - Result: Average ~5 bits/param with <0.5% quality loss

---

## Question 33: Multi-Model Orchestration and Routing
**Difficulty: Staff Level | Topic: System Design | Asked at: OpenAI, Anthropic, Microsoft**

Design a system that intelligently routes requests to different model sizes (7B, 13B, 70B, 405B) based on query complexity, latency requirements, and cost constraints. How do you determine which model to use without running all of them?

### Expected Answer:

**Intelligent Model Router Architecture:**

1. **System Overview:**
   ```
   ┌─────────────────────────────────────────────────────┐
   │                   Model Router                        │
   ├─────────────────────────────────────────────────────┤
   │ Complexity Classifier │ Load Balancer │ Cost Tracker │
   └──────────┬────────────┴───────┬───────┴──────┬──────┘
              │                    │              │
      ┌───────▼──────┐    ┌──────▼─────┐  ┌────▼──────┐
      │ 7B (Fast)     │    │ 70B (Smart) │  │405B (Best)│
      │ Simple Q&A    │    │ Complex     │  │ Hardest   │
      │ <100ms, $0.01│    │ <2s, $0.10 │  │ <10s,$1.00│
      └──────────────┘    └────────────┘  └───────────┘
   ```

2. **Complexity Classifier (Lightweight Router Model):**
   ```python
   class QueryComplexityClassifier:
       """
       Small BERT-based classifier (~50M params) that predicts 
       which model tier is needed. Trained on (query, best_model) pairs.
       Inference: <5ms overhead.
       """
       def __init__(self):
           self.classifier = load_model('complexity_classifier_v3')
           self.features = FeatureExtractor()
       
       def classify(self, query: str, context: dict) -> ModelTier:
           features = self.features.extract(query)
           # Features include:
           # - Query length, vocabulary complexity
           # - Presence of reasoning keywords ("analyze", "compare", "prove")
           # - Domain detection (code, math, creative, factual)
           # - Required output length estimate
           # - Conversation history complexity
           
           scores = self.classifier.predict(features)
           # Returns: {7B: 0.1, 13B: 0.3, 70B: 0.5, 405B: 0.1}
           
           return self.apply_routing_policy(scores, context)
       
       def apply_routing_policy(self, scores, context):
           """Apply business rules on top of classifier."""
           # SLA override: if latency_budget < 200ms, force 7B/13B
           if context.get('latency_budget_ms', 5000) < 200:
               return ModelTier.SMALL
           
           # Cost cap: if user has hit daily budget, downgrade
           if context.get('daily_cost') > context.get('daily_budget'):
               return ModelTier.SMALL
           
           # Quality-critical: specific use cases always get large model
           if context.get('use_case') in ['legal', 'medical', 'financial']:
               return ModelTier.LARGE
           
           # Default: use classifier recommendation
           return max(scores, key=scores.get)
   ```

3. **Cascade Strategy (Try Small First):**
   ```python
   class CascadeRouter:
       """
       Start with smallest model, escalate if confidence is low.
       Saves cost while maintaining quality.
       """
       def route(self, query):
           # Try 7B first (cheapest, fastest)
           response_7b = self.model_7b.generate(query)
           confidence = self.assess_confidence(response_7b)
           
           if confidence > 0.9:
               return response_7b  # Cost: $0.01
           
           # Escalate to 70B
           response_70b = self.model_70b.generate(query)
           confidence = self.assess_confidence(response_70b)
           
           if confidence > 0.85:
               return response_70b  # Cost: $0.11
           
           # Final escalation to 405B
           response_405b = self.model_405b.generate(query)
           return response_405b  # Cost: $1.11
       
       def assess_confidence(self, response):
           """
           Confidence signals:
           - Token-level entropy (low = confident)
           - Self-consistency (generate 3x, measure agreement)
           - Hallucination detector score
           - Refusal/hedging patterns
           """
           entropy = self.compute_avg_entropy(response)
           has_hedging = self.detect_hedging(response.text)
           
           confidence = 1.0 - (entropy / self.max_entropy)
           if has_hedging:
               confidence *= 0.7
           
           return confidence
   ```

4. **A/B Testing Framework for Router Optimization:**
   ```python
   class RouterExperiment:
       def __init__(self):
           self.experiment_config = {
               'control': {'router': 'classifier_v2', 'traffic': 0.8},
               'treatment_a': {'router': 'cascade_v1', 'traffic': 0.1},
               'treatment_b': {'router': 'classifier_v3', 'traffic': 0.1},
           }
       
       def evaluate_router(self, router_name, period='7d'):
           metrics = {
               'avg_quality_score': self.compute_quality(router_name),
               'p50_latency_ms': self.compute_latency(router_name, 'p50'),
               'p99_latency_ms': self.compute_latency(router_name, 'p99'),
               'cost_per_query': self.compute_cost(router_name),
               'escalation_rate': self.compute_escalations(router_name),
               'user_satisfaction': self.compute_thumbs_up_rate(router_name),
           }
           return metrics
   ```

5. **Cost Optimization Results:**
   ```
   Without routing (all queries → 70B):
   - Cost: $0.10/query × 1M queries/day = $100K/day
   - Latency: p50 = 1.5s, p99 = 5s
   
   With intelligent routing:
   - 60% → 7B ($0.01): Simple questions, lookups
   - 25% → 70B ($0.10): Complex reasoning
   - 10% → 13B ($0.03): Medium complexity
   - 5%  → 405B ($1.00): Hardest problems
   
   Weighted cost: 0.6×$0.01 + 0.1×$0.03 + 0.25×$0.10 + 0.05×$1.00
                = $0.006 + $0.003 + $0.025 + $0.05 = $0.084/query
   
   Savings: 16% cost reduction + 40% latency improvement
   Quality: <0.5% degradation (validated via blind eval)
   ```

---

## Question 34: GPU Cluster Management for ML Workloads
**Difficulty: Staff Level | Topic: Infrastructure | Asked at: NVIDIA, Meta, Google, Microsoft**

Design a GPU cluster scheduler for a mixed workload of training jobs (days-long, need all GPUs) and inference workloads (latency-sensitive, bursty). How do you handle GPU failures, preemption, and resource fragmentation?

### Expected Answer:

**GPU Cluster Scheduler Architecture:**

1. **Workload Classification & Priorities:**
   ```
   Priority Levels:
   P0 (Critical): Production inference serving (no preemption)
   P1 (High):     Fine-tuning jobs with deadlines
   P2 (Normal):   Research training experiments  
   P3 (Low):      Batch inference, evaluations
   P4 (Best-effort): Speculative experiments (preemptable)
   
   Resource Pools:
   ┌────────────────────────────────────────────┐
   │ Reserved Pool (40%): Production inference   │
   │ - Guaranteed capacity, no preemption        │
   │ - Auto-scales within pool                   │
   ├────────────────────────────────────────────┤
   │ Elastic Pool (40%): Training jobs           │
   │ - Can be reclaimed for P0 if needed         │
   │ - Checkpoints every 30 min                  │
   ├────────────────────────────────────────────┤
   │ Burst Pool (20%): Overflow / best-effort    │
   │ - Preemptable with 5-min warning            │
   │ - Spot-instance pricing internally          │
   └────────────────────────────────────────────┘
   ```

2. **Scheduler Design:**
   ```python
   class GPUClusterScheduler:
       def __init__(self, cluster_topology):
           self.topology = cluster_topology  # Nodes, GPUs, NVLink, network
           self.running_jobs = {}
           self.queue = PriorityQueue()
       
       def schedule(self, job: Job) -> Placement:
           """Find optimal GPU placement for job."""
           required_gpus = job.num_gpus
           constraints = job.constraints  # locality, interconnect, memory
           
           # Step 1: Find candidate placements
           candidates = self.find_placements(required_gpus, constraints)
           
           if not candidates:
               # No space: consider preemption
               if job.priority <= Priority.P1:
                   candidates = self.find_preemptable_placements(
                       required_gpus, job.priority
                   )
               if not candidates:
                   self.queue.put(job)
                   return None
           
           # Step 2: Rank placements by quality
           ranked = self.rank_placements(candidates, job)
           
           # Step 3: Execute placement
           best = ranked[0]
           self.execute_placement(job, best)
           return best
       
       def rank_placements(self, candidates, job):
           """Score placements based on topology awareness."""
           scores = []
           for placement in candidates:
               score = 0
               
               # Prefer GPUs on same node (NVLink communication)
               same_node_ratio = self.same_node_gpu_ratio(placement)
               score += same_node_ratio * 100
               
               # Prefer GPUs on same switch (lower network hops)
               network_diameter = self.compute_network_diameter(placement)
               score -= network_diameter * 10
               
               # Avoid fragmentation (prefer compact allocations)
               fragmentation_cost = self.estimate_fragmentation(placement)
               score -= fragmentation_cost * 50
               
               # Prefer nodes with available NVMe (for checkpointing)
               if job.needs_checkpoint:
                   nvme_available = self.check_nvme(placement)
                   score += nvme_available * 20
               
               scores.append((score, placement))
           
           return sorted(scores, reverse=True)
   ```

3. **Failure Handling:**
   ```python
   class FailureManager:
       def handle_gpu_failure(self, failed_gpu_id):
           """React to GPU failure within seconds."""
           affected_jobs = self.get_jobs_on_gpu(failed_gpu_id)
           
           for job in affected_jobs:
               if job.type == 'inference':
                   # Immediate failover: redirect traffic to replicas
                   self.redirect_traffic(job, exclude_gpu=failed_gpu_id)
                   # Background: spin up replacement on healthy GPU
                   self.spawn_replacement(job)
               
               elif job.type == 'training':
                   if job.is_elastic:
                       # Elastic training: shrink world_size, continue
                       self.shrink_training(job, remove_gpu=failed_gpu_id)
                   else:
                       # Fixed-size: restore from last checkpoint
                       self.restore_from_checkpoint(job)
                       # Find new GPU and restart
                       new_placement = self.find_replacement_gpu(job)
                       self.restart_job(job, new_placement)
       
       def proactive_migration(self):
           """Migrate jobs off GPUs showing degradation signals."""
           for gpu in self.cluster.all_gpus():
               health = self.get_gpu_health(gpu)
               if health.ecc_errors > threshold or health.temp > 85:
                   jobs = self.get_jobs_on_gpu(gpu.id)
                   for job in jobs:
                       self.live_migrate(job, target=self.find_healthy_gpu())
   ```

4. **Anti-Fragmentation Strategies:**
   ```python
   class DefragmentationEngine:
       """
       Problem: After many job completions, free GPUs are scattered
       across nodes, making large allocations impossible.
       
       Example fragmentation:
       Node 1: [USED][FREE][USED][FREE][USED][FREE][USED][FREE]
       Node 2: [FREE][USED][FREE][USED][FREE][USED][FREE][USED]
       → Cannot allocate 8-GPU job even though 8 GPUs are free!
       """
       
       def defragment(self):
           """Compact jobs to create contiguous free blocks."""
           # Find movable jobs (P3/P4 only, with checkpoints)
           movable = [j for j in self.running_jobs 
                     if j.priority >= Priority.P3 and j.has_checkpoint]
           
           # Compute optimal packing (bin-packing heuristic)
           target_layout = self.compute_compact_layout(movable)
           
           # Execute migrations during low-load window
           for job, new_placement in target_layout:
               self.checkpoint_and_migrate(job, new_placement)
       
       def gang_scheduling(self, large_job):
           """
           For jobs needing many GPUs, reserve slots as they free up.
           Prevents starvation of large jobs.
           """
           needed = large_job.num_gpus
           reserved = []
           
           # As jobs complete, reserve their GPUs
           while len(reserved) < needed:
               freed_gpu = self.wait_for_completion()
               reserved.append(freed_gpu)
               # Don't assign to other jobs
               self.mark_reserved(freed_gpu, for_job=large_job)
           
           # All GPUs collected, launch the large job
           self.launch(large_job, reserved)
   ```

5. **Monitoring & Observability:**
   ```
   Key Metrics:
   - GPU utilization (target: >85% for training, >60% for inference)
   - Scheduling delay (time in queue before execution)
   - Fragmentation index (largest contiguous block / total free)
   - Job preemption rate (target: <5% of jobs preempted)
   - Checkpoint overhead (target: <2% of training time)
   - Mean time to recovery (MTTR) after GPU failure
   - Cost per useful FLOP (excludes wasted compute)
   
   Alerts:
   - GPU utilization < 50% for > 10 min
   - Queue depth > 100 jobs
   - Fragmentation index < 0.3
   - ECC error rate increasing
   - Job failure rate > 2%
   ```

---

## Question 35: Inference Cost Optimization at Scale
**Difficulty: Staff Level | Topic: Cost Engineering | Asked at: OpenAI, Google, AWS**

Your AI product serves 100M API calls/day across multiple model sizes. Current spend is $3M/month on GPU infrastructure. Design a cost optimization strategy to reduce spend by 40% without degrading user experience.

### Expected Answer:

**Cost Optimization Framework:**

1. **Cost Breakdown Analysis:**
   ```
   Current state: $3M/month = $100K/day
   
   ┌─────────────────────────────────────────────┐
   │ Cost Distribution:                           │
   │                                              │
   │ GPU compute (inference):        60% = $1.8M  │
   │ GPU compute (training/fine-tune): 15% = $450K│
   │ Storage (models, KV cache):     10% = $300K  │
   │ Networking:                      8% = $240K  │
   │ Redundancy/failover:            7% = $210K  │
   └─────────────────────────────────────────────┘
   
   Target: $1.8M/month (40% reduction)
   → Need to save $1.2M/month
   ```

2. **Optimization Strategies (Ordered by Impact):**

   **Strategy 1: Request-Level Caching (Save $400K/month)**
   ```python
   class SemanticCache:
       """
       Cache responses for semantically similar queries.
       Hit rate: 15-30% for typical API workloads.
       """
       def __init__(self):
           self.cache = VectorDB()  # Store query embeddings + responses
           self.similarity_threshold = 0.97
       
       def get_or_generate(self, query, model):
           # Embed the query
           query_embedding = self.embed(query)
           
           # Search cache for similar queries
           matches = self.cache.search(query_embedding, top_k=1)
           
           if matches and matches[0].score > self.similarity_threshold:
               # Cache hit - return cached response (FREE)
               self.metrics.record('cache_hit')
               return matches[0].response
           
           # Cache miss - generate and cache
           response = model.generate(query)
           self.cache.insert(query_embedding, response, ttl='24h')
           return response
   ```

   **Strategy 2: Quantization (Save $350K/month)**
   ```
   Current: All models served in FP16
   Optimized:
   - 7B models: INT4 (AWQ) → 4x memory reduction → 4x more concurrent
   - 70B models: FP8 → 2x memory reduction → 2x more concurrent
   - Net: Same GPU count serves 2.5x more traffic
   - Quality loss: < 0.5% (validated)
   ```

   **Strategy 3: Smart Routing (Save $250K/month)**
   ```
   Current: 70% queries → 70B model
   Optimized: Route by complexity
   - 55% → 7B (was going to 70B unnecessarily)
   - 15% → 13B
   - 25% → 70B
   - 5%  → 405B (better quality for hard queries)
   
   Cost reduction: avg cost/query drops from $0.08 to $0.035
   ```

   **Strategy 4: Spot/Preemptible Instances (Save $150K/month)**
   ```python
   class SpotInstanceManager:
       """Use spot instances for non-latency-critical workloads."""
       
       def allocate(self, job):
           if job.type == 'batch_inference':
               # Batch jobs tolerate interruption
               return self.request_spot(job, max_price=0.4 * on_demand_price)
           elif job.type == 'eval':
               return self.request_spot(job, max_price=0.5 * on_demand_price)
           else:
               return self.request_on_demand(job)
       
       def handle_preemption(self, instance):
           """2-minute warning before spot termination."""
           job = self.get_job(instance)
           job.checkpoint()
           self.requeue(job)
   ```

   **Strategy 5: Output Length Optimization (Save $100K/month)**
   ```python
   class OutputOptimizer:
       """Many responses are unnecessarily verbose."""
       
       def optimize_max_tokens(self, query):
           # Classify expected output length
           expected_type = self.classify_output_type(query)
           
           optimal_lengths = {
               'yes_no': 10,
               'short_answer': 50,
               'explanation': 200,
               'code': 500,
               'essay': 1000,
           }
           
           return optimal_lengths.get(expected_type, 200)
   ```

3. **Implementation Roadmap:**
   ```
   Month 1: Semantic caching (Quick win, low risk)
            → Expected savings: $400K/month
   
   Month 2: Quantization rollout (INT4 for small, FP8 for large)
            → Expected savings: $350K/month
   
   Month 3: Smart routing deployment + A/B testing
            → Expected savings: $250K/month
   
   Month 4: Spot instances for batch workloads
            → Expected savings: $150K/month
   
   Total: $1.15M/month savings (38% reduction)
   Remaining gap: Covered by output length optimization
   ```

4. **Quality Guardrails:**
   ```python
   class CostQualityMonitor:
       """Ensure optimizations don't degrade quality."""
       
       def daily_quality_check(self):
           metrics = {
               'cache_quality': self.eval_cached_responses_freshness(),
               'quant_quality': self.compare_quant_vs_fp16_sample(),
               'routing_quality': self.eval_routing_accuracy(),
               'user_satisfaction': self.get_thumbs_up_rate(),
           }
           
           for metric, value in metrics.items():
               if value < self.thresholds[metric]:
                   self.alert(f'{metric} degraded: {value}')
                   self.rollback_optimization(metric)
   ```

5. **Long-term Architecture (6-12 months):**
   - Custom inference chips (TPU v5, AWS Inferentia2): 3-5x cost reduction
   - Distillation: Train task-specific small models from large model outputs
   - Prefix caching: Share KV cache across similar prompts (30% compute savings)
   - Disaggregated serving: Separate prefill (compute-bound) from decode (memory-bound)
# RAG Systems Architecture - Staff Architect Interview

## Question 36: Production RAG Pipeline Design
**Difficulty: Staff Level | Topic: Information Retrieval + LLM | Asked at: OpenAI, Anthropic, Google, Databricks**

Design a production RAG system that handles 10M documents, supports multi-modal content (text, tables, images), maintains freshness within 5 minutes, and achieves >95% answer accuracy. Address chunking strategy, retrieval, re-ranking, and hallucination prevention.

### Expected Answer:

**Production RAG Architecture:**

1. **End-to-End Pipeline:**
   ```
   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
   │  Ingestion    │───▶│  Indexing     │───▶│  Serving     │
   │  Pipeline     │    │  Pipeline     │    │  Pipeline    │
   └──────────────┘    └──────────────┘    └──────────────┘
   
   Ingestion:
   Documents → Parse → Chunk → Embed → Store (Vector DB + Doc Store)
   
   Serving:
   Query → Embed → Retrieve → Re-rank → Generate → Validate → Respond
   ```

2. **Advanced Chunking Strategy:**
   ```python
   class HierarchicalChunker:
       """
       Multi-level chunking that preserves document structure.
       Key insight: Different retrieval needs require different granularities.
       """
       def chunk_document(self, document) -> List[Chunk]:
           chunks = []
           
           # Level 1: Document-level summary (for broad questions)
           doc_summary = self.summarize(document)
           chunks.append(Chunk(
               text=doc_summary,
               level='document',
               doc_id=document.id,
               metadata={'type': 'summary'}
           ))
           
           # Level 2: Section-level chunks (for topic questions)
           sections = self.split_by_sections(document)
           for section in sections:
               chunks.append(Chunk(
                   text=section.text,
                   level='section',
                   parent_id=document.id,
                   metadata={'heading': section.heading}
               ))
           
           # Level 3: Paragraph-level with overlap (for specific facts)
           paragraphs = self.split_by_semantics(
               document, 
               target_size=512,  # tokens
               overlap=64,       # token overlap
               respect_boundaries=True  # Don't split mid-sentence
           )
           for para in paragraphs:
               chunks.append(Chunk(
                   text=para.text,
                   level='paragraph',
                   parent_id=para.section_id,
                   metadata={
                       'position': para.position,
                       'context_before': para.prev_sentence,
                       'context_after': para.next_sentence,
                   }
               ))
           
           # Level 4: Table/figure extraction (specialized)
           for table in document.tables:
               chunks.append(Chunk(
                   text=self.table_to_text(table),
                   level='table',
                   parent_id=document.id,
                   metadata={'table_markdown': table.to_markdown()}
               ))
           
           return chunks
       
       def split_by_semantics(self, document, target_size, overlap, respect_boundaries):
           """Split using embedding similarity to find natural boundaries."""
           sentences = self.sentence_tokenize(document.text)
           embeddings = self.embed_sentences(sentences)
           
           # Find points where consecutive sentence similarity drops
           similarities = [
               cosine_similarity(embeddings[i], embeddings[i+1])
               for i in range(len(embeddings)-1)
           ]
           
           # Split at low-similarity points, respecting target_size
           split_points = self.find_optimal_splits(
               similarities, 
               sentence_lengths=[len(s) for s in sentences],
               target_chunk_tokens=target_size
           )
           
           return self.create_chunks_with_overlap(sentences, split_points, overlap)
   ```

3. **Multi-Stage Retrieval:**
   ```python
   class MultiStageRetriever:
       def retrieve(self, query: str, top_k: int = 5) -> List[Chunk]:
           # Stage 1: Query expansion (improve recall)
           expanded_queries = self.expand_query(query)
           # Original: "What's the revenue growth?"
           # Expanded: ["revenue growth rate", "year over year revenue", 
           #            "financial performance metrics"]
           
           # Stage 2: Hybrid retrieval (semantic + keyword)
           semantic_results = self.vector_search(expanded_queries, top_k=50)
           keyword_results = self.bm25_search(query, top_k=50)
           
           # Reciprocal Rank Fusion
           fused = self.rrf_merge(semantic_results, keyword_results, k=60)
           
           # Stage 3: Cross-encoder re-ranking (expensive but accurate)
           reranked = self.cross_encoder_rerank(query, fused[:30])
           
           # Stage 4: Diversity filtering (avoid redundant chunks)
           diverse = self.mmr_filter(reranked, diversity_weight=0.3)
           
           return diverse[:top_k]
       
       def expand_query(self, query):
           """Use LLM to generate alternative query formulations."""
           prompt = f"""Generate 3 alternative search queries for: "{query}"
           Focus on different aspects and terminology."""
           alternatives = self.llm.generate(prompt)
           return [query] + alternatives
       
       def rrf_merge(self, *result_lists, k=60):
           """Reciprocal Rank Fusion - robust fusion of multiple rankings."""
           scores = defaultdict(float)
           for results in result_lists:
               for rank, doc in enumerate(results):
                   scores[doc.id] += 1.0 / (k + rank + 1)
           return sorted(scores.items(), key=lambda x: x[1], reverse=True)
   ```

4. **Hallucination Prevention:**
   ```python
   class HallucinationGuard:
       def validate_response(self, query, response, retrieved_chunks):
           """Multi-layer hallucination detection."""
           
           # Check 1: Attribution verification
           claims = self.extract_claims(response)
           for claim in claims:
               supported = self.verify_claim_against_sources(claim, retrieved_chunks)
               if not supported:
                   claim.mark_unsupported()
           
           # Check 2: Confidence calibration
           if self.count_unsupported(claims) / len(claims) > 0.3:
               # Too many unsupported claims - regenerate with stricter prompt
               return self.regenerate_with_citations(query, retrieved_chunks)
           
           # Check 3: Faithfulness score (NLI-based)
           faithfulness = self.nli_model.score(
               premise='\n'.join([c.text for c in retrieved_chunks]),
               hypothesis=response
           )
           
           if faithfulness < 0.7:
               return self.add_caveats(response, unsupported_claims)
           
           return response
       
       def generate_with_citations(self, query, chunks):
           """Force citation generation in output."""
           context = '\n'.join([f'[{i+1}] {c.text}' for i, c in enumerate(chunks)])
           prompt = f"""Answer based ONLY on the provided sources. 
           Cite sources using [1], [2], etc.
           If the sources don't contain the answer, say "I don't have enough information."
           
           Sources:
           {context}
           
           Question: {query}
           """
           return self.llm.generate(prompt)
   ```

5. **Freshness Architecture (5-minute SLA):**
   ```python
   class FreshnessManager:
       """Ensure index reflects document changes within 5 minutes."""
       
       def __init__(self):
           self.change_stream = ChangeDataCapture()  # CDC from source
           self.processing_queue = PriorityQueue()
       
       def process_changes(self):
           """Continuous processing of document changes."""
           for change in self.change_stream.listen():
               if change.type == 'CREATE':
                   chunks = self.chunker.chunk(change.document)
                   embeddings = self.embedder.batch_embed(chunks)
                   self.vector_db.upsert(chunks, embeddings)
               
               elif change.type == 'UPDATE':
                   # Identify affected chunks only
                   old_chunks = self.get_chunks(change.doc_id)
                   new_chunks = self.chunker.chunk(change.document)
                   diff = self.diff_chunks(old_chunks, new_chunks)
                   
                   self.vector_db.delete(diff.removed)
                   self.vector_db.upsert(diff.added)
                   self.vector_db.update(diff.modified)
               
               elif change.type == 'DELETE':
                   self.vector_db.delete_by_doc_id(change.doc_id)
               
               # Invalidate cache entries that used this document
               self.cache.invalidate_by_source(change.doc_id)
   ```

---

## Question 37: Evaluation and Testing for RAG Systems
**Difficulty: Staff Level | Topic: ML Evaluation | Asked at: Anthropic, Google, Microsoft**

How do you systematically evaluate a RAG system? Design an evaluation framework that measures retrieval quality, generation quality, and end-to-end performance. How do you handle regression testing when you change the embedding model or chunking strategy?

### Expected Answer:

**RAG Evaluation Framework:**

1. **Multi-Dimensional Metrics:**
   ```
   ┌─────────────────────────────────────────────────┐
   │           RAG Evaluation Dimensions              │
   ├─────────────────────────────────────────────────┤
   │ Retrieval Quality:                               │
   │   - Recall@K: Are relevant docs in top-K?       │
   │   - Precision@K: Are retrieved docs relevant?    │
   │   - MRR: How high is first relevant result?      │
   │   - NDCG: Quality of ranking                     │
   ├─────────────────────────────────────────────────┤
   │ Generation Quality:                              │
   │   - Faithfulness: Is answer supported by context?│
   │   - Relevance: Does answer address the query?    │
   │   - Completeness: Is the answer thorough?        │
   │   - Coherence: Is the answer well-structured?    │
   ├─────────────────────────────────────────────────┤
   │ End-to-End:                                      │
   │   - Answer correctness (vs ground truth)         │
   │   - Hallucination rate                           │
   │   - Latency (p50, p95, p99)                     │
   │   - Cost per query                              │
   └─────────────────────────────────────────────────┘
   ```

2. **Automated Evaluation Pipeline:**
   ```python
   class RAGEvaluator:
       def __init__(self):
           self.judge_model = load_model('gpt-4')  # LLM-as-judge
           self.test_set = self.load_golden_dataset()  # Human-labeled Q&A pairs
       
       def evaluate_full_pipeline(self, rag_system) -> EvalReport:
           results = []
           
           for test_case in self.test_set:
               # Run the RAG pipeline
               retrieved = rag_system.retrieve(test_case.query)
               response = rag_system.generate(test_case.query, retrieved)
               
               # Evaluate retrieval
               retrieval_metrics = self.eval_retrieval(
                   retrieved=retrieved,
                   relevant_docs=test_case.relevant_doc_ids
               )
               
               # Evaluate generation
               generation_metrics = self.eval_generation(
                   query=test_case.query,
                   response=response,
                   context=retrieved,
                   ground_truth=test_case.expected_answer
               )
               
               results.append({**retrieval_metrics, **generation_metrics})
           
           return self.aggregate_results(results)
       
       def eval_generation(self, query, response, context, ground_truth):
           """Use LLM-as-judge for generation quality."""
           # Faithfulness: Is the response grounded in context?
           faithfulness_prompt = f"""
           Context: {context}
           Response: {response}
           
           Rate faithfulness (1-5): Is every claim in the response 
           supported by the context? List unsupported claims.
           """
           faithfulness = self.judge_model.evaluate(faithfulness_prompt)
           
           # Correctness: Does it match ground truth?
           correctness_prompt = f"""
           Question: {query}
           Expected answer: {ground_truth}
           Actual answer: {response}
           
           Rate correctness (1-5): Does the actual answer convey 
           the same information as the expected answer?
           """
           correctness = self.judge_model.evaluate(correctness_prompt)
           
           return {
               'faithfulness': faithfulness.score,
               'correctness': correctness.score,
               'response_length': len(response.split()),
           }
   ```

3. **Regression Testing Framework:**
   ```python
   class RAGRegressionSuite:
       """Run when changing embedding model, chunking, or retrieval logic."""
       
       def __init__(self):
           # Golden dataset: 500+ hand-labeled examples across categories
           self.golden_set = {
               'factual_lookup': 100,      # Simple fact retrieval
               'multi_hop': 100,           # Requires combining multiple docs
               'temporal': 50,             # Time-sensitive questions
               'numerical': 50,            # Calculations from tables
               'negation': 50,             # "What is NOT true about..."
               'ambiguous': 50,            # Requires clarification
               'no_answer': 50,            # Answer not in corpus
               'adversarial': 50,          # Tricky/misleading queries
           }
       
       def run_regression(self, old_system, new_system):
           """Compare old vs new system across all test categories."""
           comparison = {}
           
           for category, test_cases in self.golden_set.items():
               old_scores = self.evaluate(old_system, test_cases)
               new_scores = self.evaluate(new_system, test_cases)
               
               comparison[category] = {
                   'old_accuracy': old_scores.mean(),
                   'new_accuracy': new_scores.mean(),
                   'delta': new_scores.mean() - old_scores.mean(),
                   'regressions': self.find_regressions(old_scores, new_scores),
                   'improvements': self.find_improvements(old_scores, new_scores),
               }
               
               # ALERT if any category regresses > 2%
               if comparison[category]['delta'] < -0.02:
                   self.alert(f"Regression in {category}: {comparison[category]['delta']:.1%}")
           
           return comparison
       
       def find_regressions(self, old_scores, new_scores):
           """Identify specific examples that got worse."""
           regressions = []
           for i, (old, new) in enumerate(zip(old_scores, new_scores)):
               if old.correct and not new.correct:
                   regressions.append({
                       'query': old.query,
                       'old_answer': old.response,
                       'new_answer': new.response,
                       'expected': old.ground_truth,
                   })
           return regressions
   ```

4. **Continuous Monitoring in Production:**
   ```python
   class RAGProductionMonitor:
       def track_live_metrics(self):
           """Real-time quality monitoring without ground truth."""
           
           # Proxy metrics (no labels needed):
           metrics = {
               # Retrieval signals
               'avg_retrieval_score': self.avg_top_k_similarity(),
               'empty_retrieval_rate': self.queries_with_no_results(),
               
               # Generation signals  
               'refusal_rate': self.count_responses_with('I don\'t know'),
               'avg_response_length': self.avg_token_count(),
               'citation_rate': self.responses_with_citations(),
               
               # User signals
               'thumbs_up_rate': self.positive_feedback_rate(),
               'follow_up_rate': self.users_who_ask_again(),  # Lower = better
               'copy_rate': self.users_who_copy_response(),   # Higher = better
           }
           
           # Statistical anomaly detection
           for metric, value in metrics.items():
               if self.is_anomalous(metric, value, window='1h'):
                   self.alert(f'{metric} anomaly: {value} vs baseline {self.baseline[metric]}')
   ```

5. **Synthetic Test Generation:**
   ```python
   class SyntheticTestGenerator:
       """Generate test cases automatically from the corpus."""
       
       def generate_test_set(self, corpus, n_questions=1000):
           test_cases = []
           
           for doc in random.sample(corpus, n_questions):
               # Generate question from document
               question = self.llm.generate(
                   f"Generate a specific question that can be answered "
                   f"using this document:\n{doc.text}\n\nQuestion:"
               )
               
               # Generate expected answer
               answer = self.llm.generate(
                   f"Based on this document:\n{doc.text}\n\n"
                   f"Answer this question: {question}"
               )
               
               test_cases.append(TestCase(
                   query=question,
                   expected_answer=answer,
                   relevant_doc_ids=[doc.id],
                   category=self.classify_question_type(question)
               ))
           
           # Human review a sample (10%) for quality
           return test_cases
   ```

---

## Question 38: Multi-Tenant RAG with Data Isolation
**Difficulty: Staff Level | Topic: Security & Architecture | Asked at: Microsoft, Salesforce, ServiceNow**

Design a multi-tenant RAG system where each tenant's data must be completely isolated, but the system shares infrastructure for cost efficiency. Address access control, embedding isolation, and preventing cross-tenant data leakage during retrieval.

### Expected Answer:

**Multi-Tenant RAG Architecture:**

1. **Isolation Levels:**
   ```
   ┌─────────────────────────────────────────────────────┐
   │ Level 1: Logical Isolation (Shared Everything)       │
   │ - Shared vector DB with tenant_id filter             │
   │ - Cheapest, highest density                          │
   │ - Risk: Filter bypass, side-channel attacks          │
   ├─────────────────────────────────────────────────────┤
   │ Level 2: Collection Isolation (Shared Cluster)       │
   │ - Separate collection/namespace per tenant           │
   │ - Moderate cost, good isolation                      │
   │ - Risk: Noisy neighbor, resource exhaustion          │
   ├─────────────────────────────────────────────────────┤
   │ Level 3: Physical Isolation (Dedicated Instances)    │
   │ - Dedicated vector DB instance per tenant            │
   │ - Expensive, perfect isolation                       │
   │ - For: Enterprise, regulated industries              │
   └─────────────────────────────────────────────────────┘
   ```

2. **Recommended Hybrid Architecture:**
   ```python
   class MultiTenantRAG:
       def __init__(self):
           # Tier assignment based on tenant plan
           self.tier_map = {
               'free': 'shared_pool',      # Level 1: filter-based
               'pro': 'dedicated_namespace', # Level 2: namespace isolation
               'enterprise': 'dedicated_instance',  # Level 3: full isolation
           }
       
       def retrieve(self, tenant_id, query, top_k=5):
           tier = self.get_tenant_tier(tenant_id)
           
           if tier == 'shared_pool':
               # CRITICAL: Always enforce tenant filter
               return self.shared_db.search(
                   vector=self.embed(query),
                   filter={'tenant_id': tenant_id},  # Mandatory filter
                   top_k=top_k
               )
           elif tier == 'dedicated_namespace':
               namespace = f'tenant_{tenant_id}'
               return self.shared_cluster.search(
                   vector=self.embed(query),
                   namespace=namespace,
                   top_k=top_k
               )
           else:
               db = self.get_dedicated_instance(tenant_id)
               return db.search(vector=self.embed(query), top_k=top_k)
       
       def ingest(self, tenant_id, documents):
           """Ingest with strict tenant tagging."""
           chunks = self.chunker.chunk(documents)
           
           # Tag EVERY chunk with tenant_id (defense in depth)
           for chunk in chunks:
               chunk.metadata['tenant_id'] = tenant_id
               chunk.metadata['ingested_at'] = time.time()
               chunk.metadata['acl'] = self.get_tenant_acl(tenant_id)
           
           embeddings = self.embed_batch(chunks)
           self.store(tenant_id, chunks, embeddings)
   ```

3. **Preventing Cross-Tenant Leakage:**
   ```python
   class IsolationGuard:
       """Defense-in-depth against cross-tenant data leakage."""
       
       def validate_retrieval(self, tenant_id, results):
           """Post-retrieval validation - catch any filter failures."""
           for result in results:
               if result.metadata.get('tenant_id') != tenant_id:
                   # CRITICAL: Log security incident, drop result
                   self.security_alert(
                       f"Cross-tenant leak detected: "
                       f"tenant {tenant_id} received doc from "
                       f"tenant {result.metadata['tenant_id']}"
                   )
                   results.remove(result)
           return results
       
       def prevent_embedding_leakage(self):
           """
           Concern: Can you reverse-engineer content from embeddings?
           Mitigation: Tenant-specific embedding perturbation.
           """
           pass  # See approach below
       
       def audit_access(self, tenant_id, query, results):
           """Complete audit trail for compliance."""
           self.audit_log.write({
               'timestamp': time.time(),
               'tenant_id': tenant_id,
               'query_hash': hash(query),  # Don't log actual query (PII)
               'result_doc_ids': [r.id for r in results],
               'result_count': len(results),
           })
   ```

4. **Shared Model with Tenant Context:**
   ```python
   class TenantAwareLLM:
       """Single LLM serving all tenants with proper isolation."""
       
       def generate(self, tenant_id, query, context):
           # Tenant-specific system prompt (configurable per tenant)
           system_prompt = self.get_tenant_system_prompt(tenant_id)
           
           # Ensure context only contains tenant's own documents
           verified_context = self.isolation_guard.validate(tenant_id, context)
           
           # Generate with strict grounding instruction
           response = self.llm.generate(
               system=system_prompt,
               context=verified_context,
               query=query,
               stop_sequences=self.get_tenant_stop_sequences(tenant_id)
           )
           
           # Post-generation PII filter
           response = self.pii_filter.scrub(response, tenant_id)
           
           return response
       
       def prevent_prompt_injection(self, tenant_id, query):
           """Prevent tenant A from crafting prompts that leak tenant B's data."""
           # Input sanitization
           sanitized = self.sanitize_input(query)
           
           # Detect injection attempts
           if self.injection_detector.is_suspicious(sanitized):
               self.security_alert(tenant_id, 'prompt_injection_attempt')
               return "I cannot process this request."
           
           return sanitized
   ```

5. **Resource Isolation & Fair Scheduling:**
   ```python
   class TenantResourceManager:
       """Prevent noisy neighbor problems."""
       
       def __init__(self):
           self.rate_limiters = {}  # Per-tenant rate limits
           self.quotas = {}        # Per-tenant storage quotas
       
       def enforce_limits(self, tenant_id, operation):
           tenant_plan = self.get_plan(tenant_id)
           
           limits = {
               'free':       {'qps': 10,  'storage_gb': 1,   'docs': 10_000},
               'pro':        {'qps': 100, 'storage_gb': 50,  'docs': 1_000_000},
               'enterprise': {'qps': 1000,'storage_gb': 500, 'docs': 10_000_000},
           }
           
           if not self.rate_limiters[tenant_id].allow(operation):
               raise RateLimitExceeded(f"Tenant {tenant_id} exceeded {limits[tenant_plan]['qps']} QPS")
   ```

---

## Question 39: Agentic RAG with Tool Use
**Difficulty: Staff Level | Topic: AI Agents | Asked at: OpenAI, Anthropic, LangChain, Google**

Design an agentic RAG system where the LLM can decide to search multiple sources, refine queries, call APIs, and synthesize information across multiple retrieval steps. How do you handle loops, token budget management, and ensuring termination?

### Expected Answer:

**Agentic RAG Architecture:**

1. **Agent Loop Design:**
   ```python
   class AgenticRAG:
       def __init__(self):
           self.tools = {
               'vector_search': VectorSearchTool(),
               'web_search': WebSearchTool(),
               'sql_query': SQLQueryTool(),
               'calculator': CalculatorTool(),
               'code_executor': CodeExecutorTool(),
           }
           self.max_iterations = 10
           self.token_budget = 32000  # Total context budget
       
       def answer(self, query: str) -> AgentResponse:
           messages = [{'role': 'user', 'content': query}]
           iteration = 0
           tokens_used = 0
           
           while iteration < self.max_iterations:
               iteration += 1
               
               # LLM decides: answer directly or use a tool
               action = self.llm.plan(messages, self.tools, self.token_budget - tokens_used)
               
               if action.type == 'final_answer':
                   return AgentResponse(
                       answer=action.content,
                       sources=self.collect_sources(messages),
                       iterations=iteration,
                       tokens_used=tokens_used
                   )
               
               elif action.type == 'tool_call':
                   # Execute the tool
                   result = self.execute_tool(action.tool, action.params)
                   
                   # Add result to context
                   messages.append({
                       'role': 'tool',
                       'tool': action.tool,
                       'content': self.truncate_if_needed(result, budget_remaining)
                   })
                   
                   tokens_used += self.count_tokens(result)
               
               # Budget check
               if tokens_used > self.token_budget * 0.9:
                   # Force final answer with what we have
                   return self.force_answer(messages)
           
           # Max iterations reached
           return self.force_answer(messages)
   ```

2. **Query Decomposition & Planning:**
   ```python
   class QueryPlanner:
       """Break complex questions into retrieval sub-tasks."""
       
       def plan(self, query: str) -> List[SubTask]:
           planning_prompt = f"""
           Decompose this question into retrieval steps:
           "{query}"
           
           For each step, specify:
           1. What information to retrieve
           2. Which tool to use (vector_search, web_search, sql_query)
           3. Dependencies on previous steps
           
           Output as JSON.
           """
           
           plan = self.llm.generate(planning_prompt)
           return self.parse_plan(plan)
       
       # Example output for "Compare Q3 revenue to competitors":
       # [
       #   {"step": 1, "action": "sql_query", "query": "SELECT revenue FROM financials WHERE quarter='Q3'", "deps": []},
       #   {"step": 2, "action": "web_search", "query": "competitor Q3 2024 revenue", "deps": []},
       #   {"step": 3, "action": "synthesize", "query": "Compare our Q3 revenue to competitors", "deps": [1, 2]}
       # ]
   ```

3. **Adaptive Retrieval (Self-Reflective RAG):**
   ```python
   class SelfReflectiveRetriever:
       """Agent evaluates its own retrieval quality and retries if needed."""
       
       def retrieve_with_reflection(self, query, max_attempts=3):
           for attempt in range(max_attempts):
               # Retrieve
               results = self.retriever.search(query, top_k=5)
               
               # Self-evaluate: Are these results sufficient?
               evaluation = self.llm.evaluate(
                   f"Query: {query}\n"
                   f"Retrieved documents: {results}\n"
                   f"Are these documents sufficient to answer the query? "
                   f"If not, what's missing?"
               )
               
               if evaluation.sufficient:
                   return results
               
               # Refine query based on what's missing
               refined_query = self.llm.generate(
                   f"Original query: {query}\n"
                   f"Gap identified: {evaluation.missing_info}\n"
                   f"Generate a better search query to find the missing information."
               )
               
               # Search again with refined query
               additional = self.retriever.search(refined_query, top_k=3)
               results.extend(additional)
               
               query = refined_query  # Update for next iteration
           
           return results
   ```

4. **Token Budget Management:**
   ```python
   class TokenBudgetManager:
       """Prevent context overflow and manage costs."""
       
       def __init__(self, total_budget=32000):
           self.total_budget = total_budget
           self.allocations = {
               'system_prompt': 500,
               'query': 200,
               'tool_results': 20000,  # Largest allocation
               'reasoning': 5000,
               'final_answer': 2000,
               'buffer': 4300,
           }
       
       def allocate_for_tool_result(self, result_text, priority='normal'):
           available = self.get_remaining_budget('tool_results')
           result_tokens = self.count_tokens(result_text)
           
           if result_tokens <= available:
               return result_text  # Fits entirely
           
           # Must compress
           if priority == 'high':
               # Summarize to fit
               return self.summarize_to_fit(result_text, available)
           else:
               # Truncate with notice
               truncated = self.truncate_tokens(result_text, available - 50)
               return truncated + "\n[TRUNCATED - request more specific query]"
       
       def should_stop(self) -> bool:
           """Signal agent to wrap up."""
           remaining = self.total_budget - self.tokens_used
           return remaining < self.allocations['final_answer'] + self.allocations['buffer']
   ```

5. **Termination Guarantees:**
   ```python
   class TerminationGuard:
       """Ensure agent always terminates in bounded time/cost."""
       
       def __init__(self):
           self.limits = {
               'max_iterations': 10,
               'max_time_seconds': 30,
               'max_tokens': 50000,
               'max_tool_calls': 15,
               'max_cost_dollars': 0.50,
           }
           self.start_time = None
           self.metrics = defaultdict(int)
       
       def check(self) -> bool:
           """Returns True if agent should terminate."""
           elapsed = time.time() - self.start_time
           
           if elapsed > self.limits['max_time_seconds']:
               return True
           if self.metrics['iterations'] >= self.limits['max_iterations']:
               return True
           if self.metrics['total_tokens'] >= self.limits['max_tokens']:
               return True
           if self.metrics['tool_calls'] >= self.limits['max_tool_calls']:
               return True
           
           return False
       
       def detect_loops(self, actions_history):
           """Detect if agent is stuck in a loop."""
           if len(actions_history) < 4:
               return False
           
           # Check for repeated tool calls with same parameters
           recent = actions_history[-4:]
           if len(set(str(a) for a in recent)) <= 2:
               return True  # Same 1-2 actions repeating
           
           return False
   ```

---

## Question 40: RAG for Structured + Unstructured Data (Text-to-SQL + Vector Search)
**Difficulty: Staff Level | Topic: Hybrid Systems | Asked at: Databricks, Snowflake, Google**

Design a unified query system that can answer questions requiring both structured data (SQL databases) and unstructured data (documents). The system should automatically determine whether to query SQL, vector search, or both, and synthesize the results.

### Expected Answer:

**Hybrid Structured + Unstructured RAG:**

1. **Architecture Overview:**
   ```
   User Query: "Which customers in the Northeast had complaints 
                about delivery delays last quarter?"
   
   ┌─────────────────────────────────────────────────────┐
   │              Query Intent Classifier                  │
   │  → Structured (SQL): customer region, time filter    │
   │  → Unstructured (RAG): complaint content analysis    │
   │  → HYBRID: Need both!                                │
   └─────────────┬────────────────────────┬───────────────┘
                 │                        │
        ┌────────▼─────────┐    ┌────────▼─────────┐
        │  Text-to-SQL     │    │  Vector Search    │
        │  "SELECT from    │    │  "delivery delay  │
        │   customers      │    │   complaints"     │
        │   WHERE region   │    │   filtered by     │
        │   ='Northeast'"  │    │   customer_ids    │
        └────────┬─────────┘    └────────┬─────────┘
                 │                        │
                 └───────────┬────────────┘
                             │
                    ┌────────▼─────────┐
                    │   Synthesizer    │
                    │   (Join + LLM)   │
                    └──────────────────┘
   ```

2. **Intent Classification & Query Planning:**
   ```python
   class HybridQueryPlanner:
       def plan(self, query: str, schema_context: str) -> QueryPlan:
           planning_prompt = f"""
           Given this user question and available data sources, 
           create an execution plan.
           
           Available SQL tables:
           {schema_context}
           
           Available document collections:
           - support_tickets (customer complaints, feedback)
           - product_docs (manuals, specs)
           - internal_wiki (policies, procedures)
           
           Question: {query}
           
           Determine:
           1. What structured data is needed? (SQL query)
           2. What unstructured data is needed? (search query)
           3. How to combine results?
           4. Execution order (parallel or sequential)?
           """
           
           plan = self.llm.generate(planning_prompt)
           return self.parse_plan(plan)
       
       # Example plan:
       # {
       #   "sql_queries": [
       #     {"query": "SELECT customer_id, name FROM customers WHERE region='Northeast'",
       #      "purpose": "Get customer list for filtering"}
       #   ],
       #   "vector_queries": [
       #     {"query": "delivery delay complaint",
       #      "collection": "support_tickets",
       #      "filters": {"date_range": "Q3 2024", "customer_ids": "$sql_result_1"},
       #      "depends_on": "sql_query_1"}
       #   ],
       #   "execution_order": "sequential",
       #   "synthesis": "List customers with their specific complaints"
       # }
   ```

3. **Text-to-SQL with Safety:**
   ```python
   class SafeTextToSQL:
       def __init__(self, db_connection, schema):
           self.db = db_connection
           self.schema = schema
           self.query_validator = SQLValidator()
       
       def generate_and_execute(self, natural_query, context=None):
           # Generate SQL
           sql = self.llm.generate(
               f"Schema:\n{self.schema}\n\n"
               f"Convert to SQL: {natural_query}\n"
               f"Rules: SELECT only, no mutations, limit 1000 rows"
           )
           
           # Validate (CRITICAL for security)
           validation = self.query_validator.validate(sql)
           if not validation.safe:
               raise SecurityError(f"Unsafe SQL: {validation.reason}")
           
           # Execute with timeout and row limit
           try:
               results = self.db.execute(sql, timeout=10, max_rows=1000)
               return SQLResult(query=sql, data=results, row_count=len(results))
           except Exception as e:
               # Self-correction: try to fix the SQL
               fixed_sql = self.llm.generate(
                   f"This SQL failed: {sql}\nError: {e}\nFix it:"
               )
               return self.db.execute(fixed_sql, timeout=10, max_rows=1000)
       
       class SQLValidator:
           def validate(self, sql: str) -> ValidationResult:
               """Prevent dangerous SQL operations."""
               dangerous_patterns = [
                   r'\bDROP\b', r'\bDELETE\b', r'\bUPDATE\b', 
                   r'\bINSERT\b', r'\bALTER\b', r'\bTRUNCATE\b',
                   r'\bEXEC\b', r'--', r'/\*', r'\bUNION\b.*\bSELECT\b'
               ]
               for pattern in dangerous_patterns:
                   if re.search(pattern, sql, re.IGNORECASE):
                       return ValidationResult(safe=False, reason=f"Matched: {pattern}")
               return ValidationResult(safe=True)
   ```

4. **Result Synthesis:**
   ```python
   class HybridResultSynthesizer:
       def synthesize(self, query, sql_results, vector_results):
           """Combine structured and unstructured results into coherent answer."""
           
           # Format SQL results as table
           sql_context = self.format_sql_results(sql_results)
           
           # Format retrieved documents
           doc_context = self.format_documents(vector_results)
           
           synthesis_prompt = f"""
           User question: {query}
           
           Structured data (from database):
           {sql_context}
           
           Relevant documents:
           {doc_context}
           
           Synthesize a comprehensive answer combining both data sources.
           Cite specific numbers from the database and quote relevant 
           document excerpts. If there are contradictions between sources,
           note them.
           """
           
           return self.llm.generate(synthesis_prompt)
       
       def format_sql_results(self, results):
           """Convert SQL results to LLM-friendly format."""
           if results.row_count > 20:
               # Summarize large result sets
               return (
                   f"Query returned {results.row_count} rows. "
                   f"Summary statistics:\n{self.compute_stats(results)}\n"
                   f"Top 10 rows:\n{results.to_markdown(limit=10)}"
               )
           return results.to_markdown()
   ```

5. **Schema-Aware Embedding for Unified Search:**
   ```python
   class UnifiedSearchIndex:
       """Index both structured schema and unstructured docs in same space."""
       
       def build_schema_embeddings(self, database_schema):
           """Embed table/column descriptions for routing."""
           schema_chunks = []
           for table in database_schema.tables:
               # Embed table description
               schema_chunks.append({
                   'text': f"Table: {table.name}. {table.description}. "
                          f"Columns: {', '.join(c.name + ': ' + c.description for c in table.columns)}",
                   'type': 'schema',
                   'table': table.name,
               })
           
           self.schema_index.upsert(schema_chunks)
       
       def route_query(self, query):
           """Determine if query needs SQL, vector search, or both."""
           # Search both schema index and document index
           schema_matches = self.schema_index.search(query, top_k=3)
           doc_matches = self.doc_index.search(query, top_k=3)
           
           schema_relevance = max(m.score for m in schema_matches) if schema_matches else 0
           doc_relevance = max(m.score for m in doc_matches) if doc_matches else 0
           
           if schema_relevance > 0.8 and doc_relevance > 0.8:
               return 'hybrid'
           elif schema_relevance > doc_relevance:
               return 'sql'
           else:
               return 'vector'
   ```
# ML Training Infrastructure - Staff Architect Interview

## Question 41: Distributed Training at Scale
**Difficulty: Staff Level | Topic: ML Infrastructure | Asked at: Meta, Google, NVIDIA, Microsoft**

Design a distributed training system for a 175B parameter model across 1024 GPUs. Explain data parallelism, tensor parallelism, pipeline parallelism, and expert parallelism (MoE). How do you handle stragglers, gradient synchronization, and checkpointing?

### Expected Answer:

**Distributed Training Architecture:**

1. **Parallelism Strategies Combined (3D Parallelism):**
   ```
   1024 GPUs organized as:
   - Data Parallel (DP): 16 replicas
   - Tensor Parallel (TP): 8 GPUs per node (NVLink)
   - Pipeline Parallel (PP): 8 stages across nodes
   
   Total: DP=16 × TP=8 × PP=8 = 1024 GPUs
   
   ┌────────── Data Parallel Group 1 ──────────┐
   │ ┌─── Pipeline Stage 1 ───┐                │
   │ │ GPU0 GPU1 GPU2 GPU3    │ (Tensor Par.)  │
   │ │ GPU4 GPU5 GPU6 GPU7    │                │
   │ └────────────────────────┘                │
   │ ┌─── Pipeline Stage 2 ───┐                │
   │ │ GPU8 GPU9 GPU10 GPU11  │                │
   │ │ GPU12 GPU13 GPU14 GPU15│                │
   │ └────────────────────────┘                │
   │ ... (8 pipeline stages)                    │
   └───────────────────────────────────────────┘
   × 16 data parallel replicas = 1024 GPUs
   ```

2. **Gradient Synchronization:**
   ```python
   class DistributedTrainer:
       def __init__(self, model, config):
           self.dp_size = config.dp_size  # 16
           self.tp_size = config.tp_size  # 8
           self.pp_size = config.pp_size  # 8
           
           # Communication groups
           self.dp_group = create_process_group(ranks=self.get_dp_peers())
           self.tp_group = create_process_group(ranks=self.get_tp_peers())
           self.pp_group = create_process_group(ranks=self.get_pp_peers())
       
       def training_step(self, batch):
           # 1. Split batch across DP dimension
           micro_batches = self.split_batch(batch, self.dp_size * self.pp_size)
           
           # 2. Pipeline schedule (1F1B - one forward, one backward)
           losses = self.pipeline_schedule(micro_batches)
           
           # 3. All-reduce gradients across DP group
           # (TP handles intra-node, PP handles inter-stage)
           for param in self.model.parameters():
               dist.all_reduce(param.grad, group=self.dp_group, op=dist.ReduceOp.AVG)
           
           # 4. Optimizer step
           self.optimizer.step()
           
           return sum(losses) / len(losses)
       
       def pipeline_schedule(self, micro_batches):
           """1F1B schedule minimizes pipeline bubble."""
           num_micro = len(micro_batches)
           num_warmup = self.pp_size - self.pp_rank - 1
           num_steady = num_micro - num_warmup
           
           losses = []
           
           # Warmup: only forward passes
           for i in range(num_warmup):
               output = self.forward_step(micro_batches[i])
               losses.append(output.loss)
           
           # Steady state: alternate 1 forward + 1 backward
           for i in range(num_steady):
               output = self.forward_step(micro_batches[num_warmup + i])
               losses.append(output.loss)
               self.backward_step(micro_batches[i])
           
           # Cooldown: only backward passes
           for i in range(num_warmup):
               self.backward_step(micro_batches[num_steady + i])
           
           return losses
   ```

3. **ZeRO (Zero Redundancy Optimizer):**
   ```python
   class ZeROOptimizer:
       """
       ZeRO Stage 3: Partition model parameters, gradients, AND optimizer states.
       Each GPU only stores 1/N of everything. All-gather when needed.
       
       Memory per GPU (175B model, FP16, 1024 GPUs):
       - Without ZeRO: 350GB (weights) + 350GB (grads) + 700GB (Adam states) = 1.4TB (impossible!)
       - ZeRO Stage 3: 1.4TB / 1024 = 1.37GB per GPU ✓ (fits in 80GB with room for activations)
       """
       
       def __init__(self, model, dp_group):
           self.dp_group = dp_group
           self.world_size = dist.get_world_size(dp_group)
           self.rank = dist.get_rank(dp_group)
           
           # Partition parameters
           self.param_partitions = self.partition_params(model)
       
       def forward_with_gather(self, module, input):
           """All-gather full parameters just-in-time for forward pass."""
           full_params = dist.all_gather(
               self.param_partitions[module], group=self.dp_group
           )
           module.load_params(full_params)
           output = module(input)
           module.free_params()  # Release full copy immediately
           return output
       
       def step(self):
           """Each GPU only updates its partition of parameters."""
           for partition_id in range(self.world_size):
               if partition_id == self.rank:
                   # This is my partition - update it
                   self.optimizer.step(self.param_partitions[partition_id])
               # Broadcast updated params to all
               dist.broadcast(self.param_partitions[partition_id], 
                            src=partition_id, group=self.dp_group)
   ```

4. **Checkpointing for Fault Tolerance:**
   ```python
   class AsyncCheckpointer:
       """
       Challenge: 175B model checkpoint = 350GB. Can't stop training for 10+ min.
       Solution: Async checkpointing with copy-on-write.
       """
       
       def __init__(self, save_interval_steps=500):
           self.interval = save_interval_steps
           self.checkpoint_executor = ThreadPoolExecutor(max_workers=2)
       
       def maybe_checkpoint(self, step, model, optimizer):
           if step % self.interval != 0:
               return
           
           # Snapshot model state (CPU copy, doesn't block training)
           state_dict = {
               'model': self.async_cpu_copy(model.state_dict()),
               'optimizer': self.async_cpu_copy(optimizer.state_dict()),
               'step': step,
               'rng_state': torch.cuda.get_rng_state(),
           }
           
           # Save in background (to distributed filesystem)
           future = self.checkpoint_executor.submit(
               self.save_checkpoint, state_dict, step
           )
           
           # Keep last 3 checkpoints, delete older
           self.cleanup_old_checkpoints(keep=3)
       
       def save_checkpoint(self, state_dict, step):
           """Distributed save: each rank saves its own shard."""
           rank = dist.get_rank()
           path = f's3://checkpoints/step_{step}/rank_{rank}.pt'
           torch.save(state_dict, path)
           
           # Rank 0 saves metadata
           if rank == 0:
               metadata = {
                   'step': step,
                   'world_size': dist.get_world_size(),
                   'timestamp': time.time(),
                   'loss': self.current_loss,
               }
               save_json(f's3://checkpoints/step_{step}/metadata.json', metadata)
       
       def restore(self, checkpoint_path):
           """Restore from checkpoint, handling world_size changes."""
           metadata = load_json(f'{checkpoint_path}/metadata.json')
           
           if metadata['world_size'] != dist.get_world_size():
               # Resharding needed (common when cluster changes)
               return self.restore_with_reshard(checkpoint_path, metadata)
           
           rank = dist.get_rank()
           state = torch.load(f'{checkpoint_path}/rank_{rank}.pt')
           return state
   ```

5. **Straggler Mitigation:**
   ```python
   class StragglerMitigation:
       """
       In 1024 GPU training, at least one GPU will be slow.
       A single slow GPU blocks all-reduce, wasting 1023 GPUs.
       """
       
       def detect_stragglers(self):
           """Monitor per-GPU step times."""
           step_times = self.collect_step_times()  # From all ranks
           median = np.median(step_times)
           
           stragglers = [
               rank for rank, time in enumerate(step_times)
               if time > median * 1.3  # 30% slower than median
           ]
           return stragglers
       
       def mitigate(self, stragglers):
           """Multiple mitigation strategies."""
           for rank in stragglers:
               # Strategy 1: Reduce batch size for slow GPU
               self.adjust_micro_batch_size(rank, factor=0.8)
               
               # Strategy 2: If persistent, exclude and use backup GPU
               if self.is_persistent_straggler(rank, window='10min'):
                   self.hot_swap_gpu(rank, replacement=self.get_spare_gpu())
               
               # Strategy 3: Gradient compression for slow network links
               if self.is_network_bottleneck(rank):
                   self.enable_gradient_compression(rank, ratio=0.1)
       
       def elastic_training(self):
           """Allow training to continue with fewer GPUs."""
           # If GPU fails, shrink DP group and continue
           # Adjust learning rate: lr_new = lr_old * (new_world_size / old_world_size)
           pass
   ```

---

## Question 42: Feature Store Design for Real-Time ML
**Difficulty: Staff Level | Topic: ML Platform | Asked at: Uber, Airbnb, Stripe, Netflix**

Design a feature store that serves features for both training (batch, historical) and inference (real-time, low-latency). How do you handle feature freshness, point-in-time correctness, and consistency between online and offline stores?

### Expected Answer:

**Feature Store Architecture:**

1. **Dual-Store Design:**
   ```
   ┌─────────────────────────────────────────────────────┐
   │                  Feature Store                        │
   ├──────────────────────┬──────────────────────────────┤
   │   Offline Store      │      Online Store             │
   │   (Training)         │      (Serving)                │
   │                      │                               │
   │   - Data Lake/DW     │   - Redis/DynamoDB            │
   │   - Full history     │   - Latest values only        │
   │   - High throughput  │   - Sub-10ms reads            │
   │   - Point-in-time    │   - Key-value lookup          │
   │     correctness      │   - Eventual consistency      │
   │   - Columnar format  │   - TTL-based expiry          │
   └──────────────────────┴──────────────────────────────┘
   
   Materialization Pipeline:
   Offline Store ──(scheduled/streaming)──▶ Online Store
   ```

2. **Point-in-Time Correctness (Training/Serving Skew Prevention):**
   ```python
   class PointInTimeJoin:
       """
       Critical: Training must use features AS THEY WERE at prediction time,
       not as they are NOW. Otherwise: data leakage / train-serve skew.
       """
       
       def get_training_features(self, entity_ids, timestamps, feature_names):
           """
           For each (entity, timestamp) pair, return feature values
           that were available AT that timestamp.
           """
           results = []
           for entity_id, ts in zip(entity_ids, timestamps):
               features = {}
               for feature in feature_names:
                   # Get the latest value BEFORE the timestamp
                   value = self.offline_store.query(
                       f"""
                       SELECT value FROM {feature.table}
                       WHERE entity_id = '{entity_id}'
                       AND event_timestamp <= '{ts}'
                       ORDER BY event_timestamp DESC
                       LIMIT 1
                       """
                   )
                   features[feature] = value
               results.append(features)
           return results
       
       def validate_no_leakage(self, feature_timestamps, label_timestamp):
           """Ensure no feature was computed AFTER the label was known."""
           for feat_ts in feature_timestamps:
               if feat_ts > label_timestamp:
                   raise DataLeakageError(
                       f"Feature timestamp {feat_ts} is after label "
                       f"timestamp {label_timestamp}"
                   )
   ```

3. **Real-Time Feature Computation:**
   ```python
   class StreamingFeatureEngine:
       """Compute features from event streams in real-time."""
       
       def __init__(self):
           self.stream_processor = FlinkJob()  # or Spark Structured Streaming
           self.aggregation_windows = ['1min', '5min', '1hr', '24hr', '7d']
       
       def define_feature(self, name, entity_key, aggregation, source_stream):
           """
           Example: user_purchase_count_1hr
           - Entity: user_id
           - Aggregation: COUNT
           - Window: 1 hour
           - Source: purchase_events stream
           """
           return StreamingFeature(
               name=name,
               entity_key=entity_key,
               aggregation=aggregation,
               source=source_stream,
               windows=self.aggregation_windows
           )
       
       def process_event(self, event):
           """Process incoming event, update all affected features."""
           entity_id = event[self.entity_key]
           
           for window in self.aggregation_windows:
               key = f"{self.name}:{entity_id}:{window}"
               
               if self.aggregation == 'count':
                   self.online_store.increment(key)
               elif self.aggregation == 'sum':
                   self.online_store.increment(key, event['amount'])
               elif self.aggregation == 'avg':
                   self.online_store.update_running_avg(key, event['value'])
               
               # Set TTL to window duration
               self.online_store.set_ttl(key, window_to_seconds(window))
           
           # Also write to offline store for historical access
           self.offline_store.append(entity_id, event, timestamp=event['ts'])
   ```

4. **Feature Consistency Monitoring:**
   ```python
   class FeatureConsistencyMonitor:
       """Detect drift between online and offline feature values."""
       
       def check_online_offline_consistency(self):
           """Periodically compare online vs offline values."""
           # Sample entities
           sample_entities = self.sample_active_entities(n=1000)
           
           discrepancies = []
           for entity_id in sample_entities:
               online_values = self.online_store.get_all_features(entity_id)
               offline_values = self.offline_store.get_latest_features(entity_id)
               
               for feature_name in online_values:
                   online_val = online_values[feature_name]
                   offline_val = offline_values.get(feature_name)
                   
                   if not self.values_match(online_val, offline_val, tolerance=0.01):
                       discrepancies.append({
                           'entity': entity_id,
                           'feature': feature_name,
                           'online': online_val,
                           'offline': offline_val,
                       })
           
           if len(discrepancies) / len(sample_entities) > 0.05:
               self.alert("Online/offline feature skew > 5%!")
           
           return discrepancies
       
       def check_feature_freshness(self):
           """Ensure online features are being updated."""
           for feature in self.registered_features:
               last_update = self.online_store.get_last_update_time(feature)
               expected_freshness = feature.sla_seconds
               
               if time.time() - last_update > expected_freshness:
                   self.alert(f"Feature {feature.name} is stale: "
                            f"last update {time.time() - last_update}s ago")
   ```

5. **Feature Registry & Discovery:**
   ```python
   class FeatureRegistry:
       """Central catalog of all features with lineage and metadata."""
       
       def register_feature(self, feature_def: FeatureDefinition):
           self.catalog.store({
               'name': feature_def.name,
               'entity': feature_def.entity_type,  # user, item, session
               'dtype': feature_def.dtype,
               'description': feature_def.description,
               'owner': feature_def.team,
               'source': feature_def.data_source,
               'freshness_sla': feature_def.freshness_sla,
               'computation': feature_def.transform_logic,
               'lineage': {
                   'upstream_tables': feature_def.dependencies,
                   'downstream_models': [],  # Auto-populated
               },
               'statistics': {
                   'mean': None, 'std': None, 'null_rate': None,
                   'distribution': None,  # Updated daily
               },
               'created_at': time.time(),
               'version': feature_def.version,
           })
       
       def search_features(self, query: str) -> List[Feature]:
           """Semantic search over feature descriptions."""
           return self.vector_index.search(query, top_k=20)
       
       def get_feature_lineage(self, feature_name):
           """Full lineage: raw data → transforms → feature → models → predictions."""
           pass
   ```

---

## Question 43: ML Model Versioning and Experiment Tracking
**Difficulty: Staff Level | Topic: MLOps | Asked at: Weights & Biases, MLflow, Google, Netflix**

Design a model registry and experiment tracking system that handles 1000+ concurrent experiments, supports model lineage from data to deployment, and enables reproducibility. How do you handle model promotion workflows and rollback?

### Expected Answer:

**Model Registry & Experiment Tracking System:**

1. **System Architecture:**
   ```
   ┌──────────────────────────────────────────────────────┐
   │                Experiment Tracking                     │
   │  (Metrics, Params, Artifacts, Code Versions)          │
   └───────────────────────┬──────────────────────────────┘
                           │ promotes
                           ▼
   ┌──────────────────────────────────────────────────────┐
   │                  Model Registry                        │
   │  (Versioned Models, Metadata, Lineage)                │
   └───────────────────────┬──────────────────────────────┘
                           │ deploys
                           ▼
   ┌──────────────────────────────────────────────────────┐
   │              Deployment Manager                        │
   │  (Canary, Shadow, A/B, Rollback)                      │
   └──────────────────────────────────────────────────────┘
   ```

2. **Experiment Tracking Schema:**
   ```python
   class ExperimentTracker:
       def create_run(self, experiment_name: str) -> Run:
           run = Run(
               id=generate_uuid(),
               experiment=experiment_name,
               # Automatic capture
               git_commit=get_current_commit(),
               git_branch=get_current_branch(),
               git_diff=get_uncommitted_changes(),
               environment={
                   'python_version': sys.version,
                   'packages': freeze_packages(),
                   'cuda_version': torch.version.cuda,
                   'gpu_type': get_gpu_info(),
               },
               code_snapshot=snapshot_source_files(),
               start_time=time.time(),
           )
           return run
       
       def log_params(self, run_id, params: dict):
           """Log hyperparameters (immutable after set)."""
           # params: learning_rate, batch_size, model_arch, etc.
           self.store.set_params(run_id, params)
       
       def log_metrics(self, run_id, metrics: dict, step: int):
           """Log time-series metrics."""
           # metrics: loss, accuracy, learning_rate (per step)
           self.store.append_metrics(run_id, metrics, step)
       
       def log_artifact(self, run_id, artifact_path, artifact_type):
           """Log model files, datasets, configs."""
           # Upload to artifact storage (S3/GCS)
           artifact_url = self.artifact_store.upload(artifact_path)
           self.store.register_artifact(run_id, artifact_url, artifact_type)
       
       def log_data_version(self, run_id, dataset_name, version_hash):
           """Track exact data used for training (reproducibility)."""
           self.store.set_data_lineage(run_id, dataset_name, version_hash)
   ```

3. **Model Promotion Workflow:**
   ```python
   class ModelPromotionPipeline:
       """
       Stages: Development → Staging → Canary → Production
       Each stage has gates that must pass before promotion.
       """
       
       STAGES = ['development', 'staging', 'canary', 'production']
       
       def promote(self, model_version: str, target_stage: str):
           current_stage = self.registry.get_stage(model_version)
           
           # Validate promotion order
           if self.STAGES.index(target_stage) - self.STAGES.index(current_stage) != 1:
               raise ValueError("Can only promote one stage at a time")
           
           # Run stage-specific gates
           gate_results = self.run_gates(model_version, target_stage)
           
           if all(g.passed for g in gate_results):
               self.registry.set_stage(model_version, target_stage)
               self.notify_stakeholders(model_version, target_stage)
           else:
               failed_gates = [g for g in gate_results if not g.passed]
               raise PromotionGateFailure(failed_gates)
       
       def run_gates(self, model_version, target_stage):
           gates = {
               'staging': [
                   self.gate_benchmark_regression(),   # No accuracy drop
                   self.gate_latency_requirement(),    # Meets SLA
                   self.gate_model_size_limit(),       # Fits in memory
                   self.gate_bias_fairness_check(),    # No bias regression
               ],
               'canary': [
                   self.gate_shadow_mode_validation(), # Tested on live traffic
                   self.gate_integration_tests(),      # Works with downstream
                   self.gate_security_scan(),          # No vulnerabilities
                   self.gate_approval_required(),      # Human sign-off
               ],
               'production': [
                   self.gate_canary_metrics_healthy(), # Canary showed no issues
                   self.gate_rollback_plan_exists(),   # Can revert if needed
                   self.gate_monitoring_configured(),  # Alerts are set up
               ],
           }
           return [gate(model_version) for gate in gates[target_stage]]
   ```

4. **Rollback Strategy:**
   ```python
   class ModelRollbackManager:
       def __init__(self):
           self.deployment_history = []  # Stack of deployed versions
       
       def deploy(self, model_version):
           """Deploy with automatic rollback capability."""
           previous_version = self.get_current_production()
           
           # Keep previous model warm (loaded, ready to serve)
           self.keep_warm(previous_version, ttl='24h')
           
           # Deploy new version
           self.deployment_history.append({
               'version': model_version,
               'deployed_at': time.time(),
               'previous': previous_version,
           })
           
           # Start automated monitoring
           self.start_canary_monitor(model_version, previous_version)
       
       def auto_rollback(self, model_version, reason):
           """Automatic rollback triggered by monitoring."""
           previous = self.get_previous_version(model_version)
           
           # Instant switch (previous model is warm)
           self.switch_traffic(to_version=previous, instant=True)
           
           # Mark version as failed
           self.registry.set_stage(model_version, 'failed')
           self.registry.add_note(model_version, f"Auto-rollback: {reason}")
           
           # Alert
           self.alert(
               severity='P1',
               message=f"Model {model_version} auto-rolled back: {reason}"
           )
       
       def canary_monitor(self, new_version, baseline_version):
           """Compare new vs baseline on live traffic."""
           metrics_new = self.collect_metrics(new_version, window='15min')
           metrics_baseline = self.get_baseline_metrics(baseline_version)
           
           # Statistical comparison
           for metric_name in ['accuracy', 'latency_p99', 'error_rate']:
               if self.is_significantly_worse(
                   metrics_new[metric_name], 
                   metrics_baseline[metric_name],
                   confidence=0.95
               ):
                   self.auto_rollback(new_version, 
                                     f"{metric_name} degraded significantly")
                   return
   ```

5. **Reproducibility Guarantees:**
   ```python
   class ReproducibilityManager:
       """Ensure any experiment can be exactly reproduced."""
       
       def capture_full_lineage(self, run_id):
           """Capture everything needed to reproduce."""
           return {
               'code': {
                   'git_repo': self.get_repo_url(),
                   'commit': self.get_commit_hash(),
                   'diff': self.get_uncommitted_diff(),
               },
               'data': {
                   'training_set': self.get_data_snapshot_id('train'),
                   'validation_set': self.get_data_snapshot_id('val'),
                   'preprocessing_version': self.get_pipeline_version(),
               },
               'environment': {
                   'docker_image': self.get_docker_image_digest(),
                   'pip_freeze': self.get_package_versions(),
                   'hardware': self.get_hardware_spec(),
               },
               'config': {
                   'hyperparameters': self.get_all_params(run_id),
                   'random_seeds': self.get_seeds(run_id),
               },
               'results': {
                   'final_metrics': self.get_final_metrics(run_id),
                   'model_checkpoints': self.get_checkpoint_urls(run_id),
               }
           }
       
       def reproduce(self, lineage_record):
           """Launch reproduction of an experiment."""
           # Checkout exact code version
           # Use exact data snapshot
           # Build exact environment (Docker)
           # Run with exact config + seeds
           pass
   ```

---

## Question 44: Data Pipeline for ML Training
**Difficulty: Staff Level | Topic: Data Engineering | Asked at: Databricks, Snowflake, Meta, Google**

Design a data pipeline that processes 100TB/day of raw data into ML-ready training datasets. Address data validation, schema evolution, deduplication, and ensuring data quality doesn't degrade model performance.

### Expected Answer:

**ML Data Pipeline Architecture:**

1. **Pipeline Overview:**
   ```
   Raw Sources          Processing              ML-Ready
   ┌─────────┐     ┌──────────────┐      ┌─────────────┐
   │ Events  │────▶│ Ingestion    │─────▶│ Bronze      │
   │ Logs    │     │ (Kafka/Kinesis)│     │ (Raw, append)│
   │ DB CDC  │     └──────────────┘      └──────┬──────┘
   │ APIs    │                                   │
   └─────────┘                                   ▼
                                          ┌─────────────┐
                                          │ Silver      │
                                          │ (Cleaned,   │
                                          │  validated) │
                                          └──────┬──────┘
                                                 │
                                                 ▼
                                          ┌─────────────┐
                                          │ Gold        │
                                          │ (Features,  │
                                          │  training   │
                                          │  datasets)  │
                                          └─────────────┘
   ```

2. **Data Validation Framework:**
   ```python
   class MLDataValidator:
       """Validate data quality before it reaches training."""
       
       def validate_batch(self, batch: DataFrame) -> ValidationReport:
           checks = []
           
           # Schema checks
           checks.append(self.check_schema(batch))
           
           # Statistical checks
           checks.append(self.check_distributions(batch))
           
           # ML-specific checks
           checks.append(self.check_label_distribution(batch))
           checks.append(self.check_feature_correlations(batch))
           checks.append(self.check_data_freshness(batch))
           
           # Anomaly detection
           checks.append(self.detect_data_anomalies(batch))
           
           report = ValidationReport(checks)
           
           if report.has_critical_failures:
               self.quarantine_batch(batch)
               self.alert("Data quality gate FAILED - batch quarantined")
           
           return report
       
       def check_distributions(self, batch):
           """Detect distribution shift vs reference data."""
           reference_stats = self.load_reference_statistics()
           
           issues = []
           for column in batch.columns:
               current_stats = compute_statistics(batch[column])
               
               # KS test for numerical columns
               if is_numerical(column):
                   ks_stat, p_value = ks_test(
                       batch[column].sample(10000),
                       reference_stats[column].sample
                   )
                   if p_value < 0.01:
                       issues.append(f"Distribution shift in {column}: "
                                   f"KS={ks_stat:.3f}, p={p_value:.4f}")
               
               # Null rate monitoring
               null_rate = batch[column].isnull().mean()
               expected_null_rate = reference_stats[column].null_rate
               if null_rate > expected_null_rate * 2:
                   issues.append(f"Null rate spike in {column}: "
                               f"{null_rate:.1%} vs expected {expected_null_rate:.1%}")
           
           return CheckResult('distributions', issues)
       
       def check_label_distribution(self, batch):
           """Ensure label balance hasn't changed dramatically."""
           label_dist = batch['label'].value_counts(normalize=True)
           expected_dist = self.reference_label_distribution
           
           # Chi-squared test
           chi2, p_value = chi_squared_test(label_dist, expected_dist)
           
           if p_value < 0.01:
               return CheckResult('label_dist', 
                   [f"Label distribution shifted: {label_dist.to_dict()}"])
           return CheckResult('label_dist', [])
   ```

3. **Schema Evolution Handling:**
   ```python
   class SchemaEvolutionManager:
       """Handle schema changes without breaking ML pipelines."""
       
       def handle_schema_change(self, old_schema, new_schema):
           changes = self.diff_schemas(old_schema, new_schema)
           
           for change in changes:
               if change.type == 'column_added':
                   # Safe: backfill with default, add to feature candidates
                   self.backfill_column(change.column, default=change.default)
                   self.notify_feature_team(f"New column available: {change.column}")
               
               elif change.type == 'column_removed':
                   # DANGEROUS: Check if any model depends on this column
                   dependent_models = self.find_dependent_models(change.column)
                   if dependent_models:
                       self.block_change(
                           f"Cannot remove {change.column}: "
                           f"used by models: {dependent_models}"
                       )
                   else:
                       self.deprecate_column(change.column)
               
               elif change.type == 'type_changed':
                   # Validate cast compatibility
                   if self.is_safe_cast(change.old_type, change.new_type):
                       self.apply_cast(change.column, change.new_type)
                   else:
                       self.block_change(f"Unsafe type change: {change}")
               
               elif change.type == 'semantic_change':
                   # Same column, different meaning (e.g., currency changed)
                   # Most dangerous: silent model degradation
                   self.version_column(change.column)
                   self.alert_all_consumers(change)
   ```

4. **Deduplication at Scale:**
   ```python
   class ScalableDeduplication:
       """Dedup 100TB/day efficiently."""
       
       def dedup_exact(self, batch):
           """Exact dedup using hash-based approach."""
           # Compute content hash for each record
           batch['content_hash'] = batch.apply(
               lambda row: hash_record(row, exclude=['timestamp', 'ingest_id']),
               axis=1
           )
           
           # Check against bloom filter (probabilistic, fast)
           new_records = []
           for record in batch.itertuples():
               if not self.bloom_filter.might_contain(record.content_hash):
                   new_records.append(record)
                   self.bloom_filter.add(record.content_hash)
               else:
                   # Might be duplicate, verify in hash store
                   if not self.hash_store.contains(record.content_hash):
                       new_records.append(record)
                       self.hash_store.add(record.content_hash)
           
           return new_records
       
       def dedup_fuzzy(self, batch, threshold=0.95):
           """Near-duplicate detection for text/unstructured data."""
           # MinHash LSH for approximate matching
           signatures = self.compute_minhash_signatures(batch)
           
           # LSH banding for candidate pairs
           candidates = self.lsh_index.query_batch(signatures)
           
           # Verify candidates with exact similarity
           duplicates = set()
           for id_a, id_b in candidates:
               sim = self.compute_similarity(batch[id_a], batch[id_b])
               if sim > threshold:
                   # Keep the newer record
                   duplicates.add(id_a if batch[id_a].ts < batch[id_b].ts else id_b)
           
           return batch.drop(duplicates)
   ```

5. **Training Dataset Versioning:**
   ```python
   class DatasetVersionManager:
       """Version datasets for reproducibility and rollback."""
       
       def create_version(self, dataset_name, query, description):
           """Create an immutable snapshot of a training dataset."""
           version = DatasetVersion(
               name=dataset_name,
               version_id=generate_version_id(),
               query=query,  # The SQL/transformation that defines this dataset
               created_at=time.time(),
               row_count=self.count_rows(query),
               schema=self.infer_schema(query),
               statistics=self.compute_statistics(query),
               lineage={
                   'source_tables': self.extract_source_tables(query),
                   'transforms': self.extract_transforms(query),
                   'filters': self.extract_filters(query),
               },
               storage_path=f's3://datasets/{dataset_name}/{version_id}/',
           )
           
           # Materialize (for reproducibility + performance)
           self.materialize(query, version.storage_path)
           
           # Register
           self.registry.register(version)
           
           return version
       
       def compare_versions(self, v1_id, v2_id):
           """Understand what changed between dataset versions."""
           v1 = self.registry.get(v1_id)
           v2 = self.registry.get(v2_id)
           
           return {
               'row_count_diff': v2.row_count - v1.row_count,
               'schema_changes': diff_schemas(v1.schema, v2.schema),
               'stat_changes': diff_statistics(v1.statistics, v2.statistics),
               'query_diff': diff_queries(v1.query, v2.query),
           }
   ```

---

## Question 45: Online Learning and Model Updates
**Difficulty: Staff Level | Topic: ML Systems | Asked at: Twitter/X, TikTok, Pinterest, Spotify**

Design a system for online/continual learning where models update in near-real-time based on user feedback. Address concept drift detection, safe model updates, and preventing catastrophic forgetting. How do you handle adversarial feedback?

### Expected Answer:

**Online Learning System Architecture:**

1. **System Overview:**
   ```
   ┌──────────────────────────────────────────────────────┐
   │                  Online Learning Loop                  │
   │                                                        │
   │  User Action → Feature → Predict → Serve → Feedback  │
   │       ▲                                        │      │
   │       │                                        ▼      │
   │  ┌─────────┐    ┌───────────┐    ┌──────────────┐   │
   │  │ Updated  │◀───│  Trainer  │◀───│  Feedback    │   │
   │  │ Model    │    │  (Online) │    │  Collector   │   │
   │  └─────────┘    └───────────┘    └──────────────┘   │
   │                        │                              │
   │                        ▼                              │
   │               ┌─────────────────┐                    │
   │               │  Safety Checks  │                    │
   │               │  (Before deploy)│                    │
   │               └─────────────────┘                    │
   └──────────────────────────────────────────────────────┘
   ```

2. **Concept Drift Detection:**
   ```python
   class ConceptDriftDetector:
       """Detect when data distribution or label relationship changes."""
       
       def __init__(self):
           self.detectors = {
               'feature_drift': ADWIN(),           # Adaptive windowing
               'prediction_drift': DDM(),          # Drift Detection Method
               'label_drift': PageHinkley(),       # Page-Hinkley test
               'performance_drift': KSWIN(),       # KS-window test
           }
       
       def update(self, features, prediction, label, timestamp):
           """Called for every labeled example."""
           # Feature drift: Are inputs changing?
           for i, feat_value in enumerate(features):
               self.detectors['feature_drift'].update(feat_value)
           
           # Prediction drift: Is model output distribution changing?
           self.detectors['prediction_drift'].update(prediction)
           
           # Performance drift: Is model accuracy degrading?
           error = int(prediction != label)
           self.detectors['performance_drift'].update(error)
           
           # Check all detectors
           alerts = {}
           for name, detector in self.detectors.items():
               if detector.detected_change():
                   alerts[name] = {
                       'type': name,
                       'severity': detector.get_severity(),
                       'timestamp': timestamp,
                       'window_stats': detector.get_stats(),
                   }
           
           if alerts:
               self.handle_drift(alerts)
       
       def handle_drift(self, alerts):
           """Response strategy based on drift type and severity."""
           if 'performance_drift' in alerts:
               severity = alerts['performance_drift']['severity']
               
               if severity == 'critical':  # >10% accuracy drop
                   # Immediate action: trigger full retrain
                   self.trigger_retrain(mode='full', priority='urgent')
               elif severity == 'warning':  # 3-10% drop
                   # Accelerate online learning rate
                   self.increase_learning_rate(factor=2.0)
                   self.expand_training_window()
               else:  # Gradual drift
                   # Normal online learning handles this
                   self.log_drift(alerts)
   ```

3. **Safe Online Update Strategy:**
   ```python
   class SafeOnlineUpdater:
       """Update model online while preventing catastrophic failures."""
       
       def __init__(self, base_model):
           self.production_model = base_model
           self.shadow_model = copy.deepcopy(base_model)  # Updated online
           self.validation_buffer = CircularBuffer(size=10000)
       
       def update(self, examples_batch):
           """Update shadow model, validate, then promote."""
           # Update shadow model with new examples
           self.shadow_model.partial_fit(
               examples_batch.features,
               examples_batch.labels,
               learning_rate=self.adaptive_lr()
           )
           
           # Validate against holdout buffer
           val_metrics = self.validate(self.shadow_model, self.validation_buffer)
           prod_metrics = self.validate(self.production_model, self.validation_buffer)
           
           # Promote only if shadow is better (or not significantly worse)
           if val_metrics.accuracy >= prod_metrics.accuracy - 0.005:
               self.promote_shadow_to_production()
           else:
               # Rollback shadow to production state
               self.shadow_model = copy.deepcopy(self.production_model)
               self.log_rejected_update(val_metrics, prod_metrics)
       
       def adaptive_lr(self):
           """Reduce learning rate over time to prevent oscillation."""
           updates_today = self.get_update_count_today()
           base_lr = 0.001
           # Decay: lr = base_lr / (1 + updates/100)
           return base_lr / (1 + updates_today / 100)
       
       def prevent_catastrophic_forgetting(self, new_examples):
           """Mix new examples with replay buffer of historical examples."""
           replay_examples = self.replay_buffer.sample(
               n=len(new_examples) * 3  # 3:1 replay ratio
           )
           mixed_batch = concatenate([new_examples, replay_examples])
           return shuffle(mixed_batch)
   ```

4. **Adversarial Feedback Protection:**
   ```python
   class AdversarialFeedbackFilter:
       """
       Prevent malicious users from poisoning the model through
       coordinated false feedback.
       """
       
       def filter_feedback(self, feedback_batch):
           clean_feedback = []
           
           for feedback in feedback_batch:
               # Check 1: Rate limiting per user
               if self.user_rate_exceeded(feedback.user_id):
                   continue
               
               # Check 2: Consistency check (does this user's feedback
               # match their behavioral signals?)
               if not self.is_consistent(feedback):
                   self.flag_suspicious(feedback)
                   continue
               
               # Check 3: Anomaly detection (is this feedback an outlier
               # compared to other users on same item?)
               if self.is_anomalous_feedback(feedback):
                   self.quarantine(feedback)
                   continue
               
               # Check 4: Source credibility (user trust score)
               if self.get_user_trust_score(feedback.user_id) < 0.3:
                   # Weight this feedback lower, don't exclude
                   feedback.weight = 0.1
               
               clean_feedback.append(feedback)
           
           # Check 5: Batch-level anomaly
           # If >20% of batch is from same IP/region/pattern → suspicious
           if self.detect_coordinated_attack(clean_feedback):
               self.alert("Possible coordinated feedback attack")
               return []  # Reject entire batch
           
           return clean_feedback
       
       def is_consistent(self, feedback):
           """Check if explicit feedback matches implicit signals."""
           # Example: User says "not relevant" but spent 5 minutes reading
           implicit_signal = self.get_implicit_signal(
               feedback.user_id, feedback.item_id
           )
           explicit_signal = feedback.label
           
           # If strong disagreement, flag
           if implicit_signal > 0.8 and explicit_signal < 0.2:
               return False
           return True
   ```

5. **A/B Testing for Online Learning Variants:**
   ```python
   class OnlineLearningExperiment:
       """Compare different online learning strategies."""
       
       def __init__(self):
           self.variants = {
               'control': {
                   'model': StaticModel(),  # No online updates
                   'traffic': 0.2,
               },
               'slow_update': {
                   'model': OnlineModel(update_freq='hourly'),
                   'traffic': 0.3,
               },
               'fast_update': {
                   'model': OnlineModel(update_freq='5min'),
                   'traffic': 0.3,
               },
               'continuous': {
                   'model': OnlineModel(update_freq='per_batch'),
                   'traffic': 0.2,
               },
           }
       
       def evaluate(self, window='7d'):
           results = {}
           for variant_name, config in self.variants.items():
               results[variant_name] = {
                   'ctr': self.compute_ctr(variant_name, window),
                   'revenue': self.compute_revenue(variant_name, window),
                   'latency': self.compute_latency(variant_name, window),
                   'model_stability': self.compute_prediction_variance(variant_name),
                   'drift_response_time': self.measure_adaptation_speed(variant_name),
               }
           return results
   ```
# Fine-Tuning and Training Infrastructure (Questions 111-115)

## Q111: Design a fine-tuning pipeline for enterprise customers

### Problem
Allow enterprise customers to customize models on their data without compromising model security or other tenants' data.

### Architecture

```
┌────────────────────────────────────────────────────────────────┐
│           Multi-Tenant Fine-Tuning Platform                      │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Tenant A (Isolated)        Tenant B (Isolated)          │   │
│  │  ┌────────────────┐        ┌────────────────┐           │   │
│  │  │ Data Vault     │        │ Data Vault     │           │   │
│  │  │ (encrypted,    │        │ (encrypted,    │           │   │
│  │  │  tenant-key)   │        │  tenant-key)   │           │   │
│  │  └───────┬────────┘        └───────┬────────┘           │   │
│  └──────────┼──────────────────────────┼────────────────────┘   │
│             │                          │                        │
│             ▼                          ▼                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Training Orchestrator                        │   │
│  │  ┌───────────┐  ┌──────────────┐  ┌────────────────┐   │   │
│  │  │ Data      │  │ Training Job │  │ Model          │   │   │
│  │  │ Validator │  │ Scheduler    │  │ Registry       │   │   │
│  │  └───────────┘  └──────────────┘  └────────────────┘   │   │
│  └─────────────────────────────────────────────────────────┘   │
│             │                                                   │
│             ▼                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │         Isolated Training Environment                    │   │
│  │  ┌──────────────────┐   ┌──────────────────────────┐   │   │
│  │  │ GPU Cluster      │   │ No network egress        │   │   │
│  │  │ (dedicated/spot) │   │ Encrypted memory          │   │   │
│  │  └──────────────────┘   └──────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────┘   │
│             │                                                   │
│             ▼                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐   │   │
│  │  │ Eval Suite   │  │ Safety Check │  │ Deployment  │   │   │
│  │  │ (auto)       │  │ (guardrails) │  │ (serving)   │   │   │
│  │  └──────────────┘  └──────────────┘  └─────────────┘   │   │
│  └─────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
from dataclasses import dataclass
from typing import Optional
from enum import Enum

class IsolationLevel(Enum):
    SHARED_CLUSTER = "shared"       # LoRA adapters, shared base model
    DEDICATED_NODES = "dedicated"   # Own GPU nodes, own model copy
    AIR_GAPPED = "air_gapped"      # No internet, hardware isolation

@dataclass
class FineTuneJobConfig:
    tenant_id: str
    base_model: str
    dataset_uri: str  # encrypted blob storage path
    method: str  # "lora", "qlora", "full"
    hyperparams: dict
    isolation_level: IsolationLevel
    eval_dataset_uri: Optional[str] = None
    max_epochs: int = 3
    budget_gpu_hours: float = 10.0

class EnterpriseFinetuningPipeline:
    def __init__(self, scheduler, model_registry, security_service):
        self.scheduler = scheduler
        self.model_registry = model_registry
        self.security = security_service

    async def submit_job(self, config: FineTuneJobConfig) -> str:
        """Submit a fine-tuning job with full isolation guarantees."""
        
        # 1. Validate data access (tenant can only access their data)
        assert self.security.verify_data_ownership(config.tenant_id, config.dataset_uri)
        
        # 2. Validate and scan dataset
        validation = await self._validate_dataset(config)
        if not validation.passed:
            raise DataValidationError(validation.errors)
        
        # 3. Create isolated training environment
        env = await self._create_environment(config)
        
        # 4. Schedule training job
        job_id = await self.scheduler.submit(
            image="training-runtime:latest",
            gpu_type="A100-80GB",
            gpu_count=self._calculate_gpus(config),
            environment=env,
            config={
                "base_model": config.base_model,
                "dataset": config.dataset_uri,
                "method": config.method,
                "hyperparams": config.hyperparams,
                "max_epochs": config.max_epochs,
            },
            constraints={
                "no_network_egress": True,
                "encrypted_memory": config.isolation_level != IsolationLevel.SHARED_CLUSTER,
                "max_gpu_hours": config.budget_gpu_hours,
                "tenant_isolation": config.isolation_level.value,
            }
        )
        
        return job_id

    async def _validate_dataset(self, config: FineTuneJobConfig):
        """Validate dataset quality and safety."""
        return await DataValidator(
            checks=[
                FormatCheck(expected="jsonl"),
                SizeCheck(min_examples=100, max_examples=1_000_000),
                PIICheck(action="warn"),  # flag but don't block
                ToxicityCheck(threshold=0.1),  # reject if >10% toxic
                DuplicateCheck(max_dup_ratio=0.3),
                SchemaCheck(required_fields=["messages"]),
            ]
        ).validate(config.dataset_uri)

    async def _create_environment(self, config: FineTuneJobConfig) -> dict:
        """Create isolated environment based on isolation level."""
        if config.isolation_level == IsolationLevel.SHARED_CLUSTER:
            return {
                "type": "kubernetes_pod",
                "namespace": f"tenant-{config.tenant_id}",
                "network_policy": "deny-all-egress",
                "resource_quota": {"gpu": 4, "memory": "320Gi"},
            }
        elif config.isolation_level == IsolationLevel.DEDICATED_NODES:
            return {
                "type": "dedicated_node_pool",
                "node_selector": f"tenant={config.tenant_id}",
                "encryption": "aes-256-gcm",
                "data_residency": config.hyperparams.get("region", "us-east-1"),
            }
        else:  # AIR_GAPPED
            return {
                "type": "air_gapped_cluster",
                "hardware_isolation": True,
                "no_shared_resources": True,
            }

    async def on_job_complete(self, job_id: str, config: FineTuneJobConfig):
        """Post-training: evaluate, safety check, register."""
        # Run evaluation suite
        eval_results = await self._evaluate_model(job_id, config)
        
        # Safety checks: ensure fine-tuned model doesn't produce harmful content
        safety_results = await self._safety_check(job_id)
        
        if eval_results.passed and safety_results.passed:
            # Register model (LoRA adapter or full weights)
            model_id = await self.model_registry.register(
                tenant_id=config.tenant_id,
                base_model=config.base_model,
                adapter_path=f"s3://models/{config.tenant_id}/{job_id}/",
                eval_metrics=eval_results.metrics,
                access_control={"tenant_only": config.tenant_id}
            )
            return model_id
        else:
            await self._notify_failure(config.tenant_id, eval_results, safety_results)
```

### Security Isolation Comparison

| Aspect | Shared Cluster | Dedicated Nodes | Air-Gapped |
|--------|---------------|-----------------|------------|
| Data isolation | Namespace + encryption | Node-level | Hardware |
| Compute isolation | Pod limits | Dedicated GPUs | Dedicated rack |
| Network | Pod network policy | VLAN isolation | No network |
| Cost (relative) | 1x | 3x | 10x |
| Compliance | SOC2 | HIPAA | FedRAMP High |

### Production Considerations
- **Data lifecycle**: Training data deleted after job + 7-day retention; only adapter/weights kept
- **Model security**: Adapters encrypted at rest with tenant-specific keys; cannot be exported without approval
- **Base model protection**: Tenant never gets full base model weights; only adapter deltas
- **Cost visibility**: Per-tenant metering of GPU hours, storage, inference
- **Abort/resume**: Jobs checkpointed every epoch; can resume after preemption

---

## Q112: Design a continuous fine-tuning system

### Problem
Automatically retrain models based on user feedback and production data with quality filters and regression prevention.

### Architecture

```
┌────────────────────────────────────────────────────────────┐
│            Continuous Fine-Tuning System                     │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌────────────┐    ┌──────────────┐    ┌───────────────┐  │
│  │ Production │    │  Feedback    │    │  Data Quality │  │
│  │ Traffic    │───▶│  Collector   │───▶│  Pipeline     │  │
│  └────────────┘    └──────────────┘    └───────────────┘  │
│                                               │            │
│                                               ▼            │
│                                        ┌──────────────┐   │
│                                        │  Training    │   │
│                                        │  Data Store  │   │
│                                        └──────────────┘   │
│                                               │            │
│                    ┌──────────────────────────┐            │
│                    │  Training Trigger         │            │
│                    │  (schedule/threshold)     │            │
│                    └──────────────────────────┘            │
│                              │                             │
│                              ▼                             │
│  ┌──────────────────────────────────────────────────────┐ │
│  │              Training + Evaluation Loop                │ │
│  │                                                       │ │
│  │  Train ──▶ Eval (holdout) ──▶ Regression Check ──▶   │ │
│  │     ──▶ Safety Check ──▶ Shadow Deploy ──▶ Promote   │ │
│  └──────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────┘
```

### Implementation

```python
from dataclasses import dataclass
from typing import List
import numpy as np

@dataclass
class FeedbackSignal:
    request_id: str
    input_text: str
    model_output: str
    signal_type: str  # "thumbs_up", "thumbs_down", "edit", "regenerate"
    corrected_output: str = None  # if user edited
    timestamp: float = 0

class ContinuousFineTuning:
    def __init__(self, model_registry, trainer, evaluator):
        self.model_registry = model_registry
        self.trainer = trainer
        self.evaluator = evaluator
        self.data_buffer = []
        self.training_threshold = 1000  # min new examples before retraining

    async def ingest_feedback(self, feedback: FeedbackSignal):
        """Process and filter feedback into training data."""
        # Quality filters
        if not self._passes_quality_checks(feedback):
            return
        
        # Convert to training example
        example = self._feedback_to_training_example(feedback)
        if example:
            self.data_buffer.append(example)
        
        # Check if we should trigger training
        if len(self.data_buffer) >= self.training_threshold:
            await self._trigger_training()

    def _passes_quality_checks(self, feedback: FeedbackSignal) -> bool:
        """Filter out low-quality feedback."""
        checks = [
            len(feedback.input_text) > 10,  # not trivial
            len(feedback.model_output) > 5,  # not empty
            not self._is_duplicate(feedback),  # not spam
            not self._contains_pii(feedback),  # no PII in training data
            self._is_consistent(feedback),  # corrected output makes sense
        ]
        return all(checks)

    def _feedback_to_training_example(self, feedback: FeedbackSignal) -> dict:
        """Convert feedback signals to training format."""
        if feedback.signal_type == "thumbs_up":
            return {
                "messages": [
                    {"role": "user", "content": feedback.input_text},
                    {"role": "assistant", "content": feedback.model_output}
                ],
                "weight": 1.0
            }
        elif feedback.signal_type == "edit" and feedback.corrected_output:
            return {
                "messages": [
                    {"role": "user", "content": feedback.input_text},
                    {"role": "assistant", "content": feedback.corrected_output}
                ],
                "weight": 2.0  # edits are high-signal
            }
        elif feedback.signal_type == "thumbs_down":
            # Use as negative example in DPO training
            return {
                "type": "preference",
                "prompt": feedback.input_text,
                "rejected": feedback.model_output,
                "chosen": None  # will be filled by human labeler or AI
            }
        return None

    async def _trigger_training(self):
        """Run training pipeline with regression prevention."""
        current_model = await self.model_registry.get_production()
        
        # 1. Prepare datasets
        train_data, val_data = self._split_data(self.data_buffer, val_ratio=0.2)
        
        # 2. Baseline evaluation (current model)
        baseline_metrics = await self.evaluator.evaluate(
            model=current_model,
            eval_set=val_data + self._get_regression_set()
        )
        
        # 3. Fine-tune
        new_model = await self.trainer.train(
            base_model=current_model,
            train_data=train_data,
            method="lora",
            hyperparams={"lr": 1e-5, "epochs": 2, "warmup_ratio": 0.1}
        )
        
        # 4. Evaluate new model
        new_metrics = await self.evaluator.evaluate(
            model=new_model,
            eval_set=val_data + self._get_regression_set()
        )
        
        # 5. Regression check
        if self._has_regression(baseline_metrics, new_metrics):
            await self._alert("Training produced regression", {
                "baseline": baseline_metrics,
                "new": new_metrics
            })
            return  # Do not deploy
        
        # 6. Shadow deployment
        await self.model_registry.deploy_shadow(new_model)
        
        # 7. After 24h shadow period with no issues, promote
        # (handled by separate shadow evaluation service)
        
        self.data_buffer = []  # clear buffer

    def _has_regression(self, baseline: dict, new: dict) -> bool:
        """Check if any critical metric degraded significantly."""
        critical_metrics = ["accuracy", "safety_score", "coherence"]
        for metric in critical_metrics:
            if new.get(metric, 0) < baseline.get(metric, 0) - 0.02:  # >2% drop
                return True
        return False

    def _get_regression_set(self) -> list:
        """Golden test set that must never degrade."""
        # Curated set of 500 examples covering critical scenarios
        return self.evaluator.load_golden_set("regression_v2")
```

### Training Trigger Strategy

| Trigger | Condition | Rationale |
|---------|-----------|-----------|
| Volume | 1000+ new examples | Statistical significance |
| Time | Weekly (if >100 examples) | Regular cadence |
| Quality drop | Production metrics drop >5% | Reactive fix |
| Domain shift | Embedding drift detected | Adaptation needed |

### Production Considerations
- **Data flywheel**: More usage → more feedback → better model → more usage
- **Catastrophic forgetting**: Always mix new data with 20% of original training data
- **A/B test new model**: Don't just shadow; A/B test with 10% of traffic before full promotion
- **Rollback speed**: Keep last 5 model versions hot; rollback in <60 seconds
- **Bias monitoring**: Track per-demographic performance; reject models that increase disparity

---

## Q113: Design a RLHF pipeline at scale

### Problem
Collect preference data and use reinforcement learning from human feedback to align models with business objectives.

### Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                    RLHF Pipeline at Scale                        │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Phase 1: Data Collection                                       │
│  ┌────────────┐   ┌──────────────┐   ┌────────────────────┐   │
│  │ Production │   │  Annotation  │   │  Quality Control   │   │
│  │ Sampling   │──▶│  Platform    │──▶│  (agreement, IAA)  │   │
│  └────────────┘   └──────────────┘   └────────────────────┘   │
│                                               │                 │
│  Phase 2: Reward Modeling                     ▼                 │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  ┌────────────────┐    ┌────────────────────────────┐  │    │
│  │  │ Preference Data│───▶│ Reward Model Training      │  │    │
│  │  │ (chosen/reject)│    │ (Bradley-Terry)            │  │    │
│  │  └────────────────┘    └────────────────────────────┘  │    │
│  └────────────────────────────────────────────────────────┘    │
│                              │                                  │
│  Phase 3: Policy Optimization│                                  │
│  ┌───────────────────────────┴────────────────────────────┐    │
│  │  ┌──────────────┐   ┌───────────┐   ┌──────────────┐  │    │
│  │  │  PPO / DPO   │   │  KL       │   │  Eval &      │  │    │
│  │  │  Optimizer   │──▶│  Penalty   │──▶│  Iteration   │  │    │
│  │  └──────────────┘   └───────────┘   └──────────────┘  │    │
│  └────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
from dataclasses import dataclass
from typing import List, Tuple
import torch

@dataclass
class PreferencePair:
    prompt: str
    chosen: str  # preferred response
    rejected: str  # dispreferred response
    annotator_id: str
    confidence: float  # 1-5
    category: str  # "helpfulness", "safety", "accuracy"

class RLHFPipeline:
    def __init__(self, base_model, reward_model_config, ppo_config):
        self.base_model = base_model
        self.rm_config = reward_model_config
        self.ppo_config = ppo_config

    # ─── Phase 1: Data Collection ───
    
    async def collect_preferences(self, batch_size: int = 1000) -> List[PreferencePair]:
        """Sample production queries and collect human preferences."""
        # Sample diverse prompts from production
        prompts = await self._sample_production_prompts(batch_size)
        
        # Generate multiple responses per prompt
        response_pairs = []
        for prompt in prompts:
            responses = await self._generate_candidates(prompt, n=4)
            # Create pairwise comparisons
            pairs = self._create_pairs(prompt, responses)
            response_pairs.extend(pairs)
        
        # Send to annotation platform
        annotations = await self._annotate(response_pairs)
        
        # Quality control
        filtered = self._quality_filter(annotations)
        return filtered

    def _quality_filter(self, annotations: List[PreferencePair]) -> List[PreferencePair]:
        """Filter based on inter-annotator agreement."""
        # Require >= 2 annotators to agree on each pair
        grouped = self._group_by_prompt(annotations)
        high_quality = []
        for prompt, pairs in grouped.items():
            if len(pairs) >= 2:
                agreement = self._compute_agreement(pairs)
                if agreement >= 0.7:  # 70% agreement threshold
                    high_quality.append(self._majority_choice(pairs))
        return high_quality

    # ─── Phase 2: Reward Model Training ───
    
    def train_reward_model(self, preferences: List[PreferencePair]):
        """Train reward model using Bradley-Terry model."""
        # Architecture: same as base model but with scalar head
        reward_model = RewardModel(self.base_model, scalar_head=True)
        
        optimizer = torch.optim.AdamW(reward_model.parameters(), lr=1e-5)
        
        for epoch in range(self.rm_config["epochs"]):
            for batch in self._batch_preferences(preferences):
                # Forward pass on chosen and rejected
                chosen_rewards = reward_model(batch.chosen_ids)
                rejected_rewards = reward_model(batch.rejected_ids)
                
                # Bradley-Terry loss: maximize P(chosen > rejected)
                loss = -torch.log(
                    torch.sigmoid(chosen_rewards - rejected_rewards)
                ).mean()
                
                # Regularization: keep rewards bounded
                loss += 0.01 * (chosen_rewards**2 + rejected_rewards**2).mean()
                
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
            
            # Eval: accuracy on held-out preference pairs
            accuracy = self._eval_reward_model(reward_model)
            if accuracy < 0.60:  # worse than random
                raise TrainingFailure("Reward model not learning")
        
        return reward_model

    # ─── Phase 3: Policy Optimization (DPO - simpler than PPO) ───
    
    def train_dpo(self, preferences: List[PreferencePair]):
        """Direct Preference Optimization - no separate reward model needed."""
        policy = self.base_model
        ref_model = self.base_model.copy()  # frozen reference
        ref_model.eval()
        
        optimizer = torch.optim.AdamW(policy.parameters(), lr=5e-7)
        beta = 0.1  # KL penalty strength
        
        for batch in self._batch_preferences(preferences):
            # Log probs under policy
            pi_chosen = policy.log_prob(batch.chosen_ids)
            pi_rejected = policy.log_prob(batch.rejected_ids)
            
            # Log probs under reference (frozen)
            with torch.no_grad():
                ref_chosen = ref_model.log_prob(batch.chosen_ids)
                ref_rejected = ref_model.log_prob(batch.rejected_ids)
            
            # DPO loss
            chosen_ratio = pi_chosen - ref_chosen
            rejected_ratio = pi_rejected - ref_rejected
            
            loss = -torch.log(
                torch.sigmoid(beta * (chosen_ratio - rejected_ratio))
            ).mean()
            
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(policy.parameters(), 1.0)
            optimizer.step()

    # ─── PPO Alternative ───
    
    def train_ppo(self, reward_model):
        """PPO training with KL constraint."""
        policy = self.base_model
        ref_model = self.base_model.copy()
        
        for iteration in range(self.ppo_config["iterations"]):
            # Generate responses
            prompts = self._sample_prompts(batch_size=64)
            responses = policy.generate(prompts)
            
            # Score with reward model
            rewards = reward_model.score(prompts, responses)
            
            # KL penalty to prevent reward hacking
            kl_div = self._compute_kl(policy, ref_model, prompts, responses)
            adjusted_rewards = rewards - self.ppo_config["kl_coeff"] * kl_div
            
            # PPO update
            self._ppo_step(policy, prompts, responses, adjusted_rewards)
            
            # Monitor for reward hacking
            if rewards.mean() > self.ppo_config["reward_cap"]:
                print("Warning: possible reward hacking detected")
                break
```

### DPO vs PPO Trade-offs

| Aspect | DPO | PPO |
|--------|-----|-----|
| Complexity | Simple (single loss) | Complex (RL loop) |
| Stability | Very stable | Can be unstable |
| Reward model needed | No | Yes |
| Quality ceiling | Slightly lower | Higher with good RM |
| Compute cost | 1x | 4-8x |
| Recommended for | Most use cases | Max quality when budget allows |

### Production Considerations
- **Annotation quality**: Pay $15-25/hr for expert annotators; cheaper crowd-sourcing introduces noise
- **Preference categories**: Separate reward models for helpfulness, safety, factuality
- **Reward hacking prevention**: Monitor KL divergence; cap reward; human eval every iteration
- **Data freshness**: Re-collect preferences quarterly as user expectations evolve
- **Business alignment**: Include business-specific preferences (tone, compliance, style)

---

## Q114: Design distributed training infrastructure for 70B parameter models

### Problem
Fine-tune 70B parameter models with data parallelism, model parallelism, memory optimization, and failure recovery.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│          Distributed Training Infrastructure (70B)           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              Training Coordinator                       │ │
│  │  ┌───────────┐  ┌────────────┐  ┌─────────────────┐  │ │
│  │  │ Job       │  │ Checkpoint │  │ Failure         │  │ │
│  │  │ Scheduler │  │ Manager    │  │ Detector        │  │ │
│  │  └───────────┘  └────────────┘  └─────────────────┘  │ │
│  └────────────────────────────────────────────────────────┘ │
│                          │                                   │
│  ┌────────────────────────────────────────────────────────┐ │
│  │            Parallelism Strategy                         │ │
│  │                                                         │ │
│  │  Node 0 (8x A100)     Node 1 (8x A100)                │ │
│  │  ┌─┬─┬─┬─┬─┬─┬─┬─┐  ┌─┬─┬─┬─┬─┬─┬─┬─┐             │ │
│  │  │0│1│2│3│4│5│6│7│  │0│1│2│3│4│5│6│7│             │ │
│  │  └─┴─┴─┴─┴─┴─┴─┴─┘  └─┴─┴─┴─┴─┴─┴─┴─┘             │ │
│  │  ◄── Tensor Parallel ──▶  ◄── Tensor Parallel ──▶      │ │
│  │  ◄──────────── Data Parallel ─────────────────▶        │ │
│  │                                                         │ │
│  │  ZeRO Stage 3: Partition optimizer + gradients + params │ │
│  └────────────────────────────────────────────────────────┘ │
│                          │                                   │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Memory Optimization Stack                              │ │
│  │  [LoRA/QLoRA] [Gradient Checkpointing] [Mixed Prec.]  │ │
│  │  [Flash Attention] [Activation Offloading]              │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Implementation

```python
import torch
from torch.distributed import init_process_group
from dataclasses import dataclass

@dataclass
class TrainingConfig:
    model_size: str  # "70B"
    num_nodes: int = 4
    gpus_per_node: int = 8
    method: str = "qlora"  # "full", "lora", "qlora"
    tensor_parallel: int = 4
    pipeline_parallel: int = 1
    data_parallel: int = 8  # total_gpus / (TP * PP)
    micro_batch_size: int = 1
    gradient_accumulation: int = 16
    max_seq_len: int = 4096
    dtype: str = "bf16"

class DistributedTrainer:
    def __init__(self, config: TrainingConfig):
        self.config = config
        self.world_size = config.num_nodes * config.gpus_per_node

    def calculate_memory_requirements(self) -> dict:
        """Estimate memory per GPU for 70B model."""
        params_billions = 70
        bytes_per_param = {"fp32": 4, "bf16": 2, "int4": 0.5}
        
        if self.config.method == "qlora":
            # Base model in 4-bit + LoRA adapters in bf16
            base_memory_gb = params_billions * bytes_per_param["int4"]  # 35 GB
            lora_memory_gb = params_billions * 0.01 * bytes_per_param["bf16"]  # ~1.4 GB (1% params)
            optimizer_memory_gb = lora_memory_gb * 8  # AdamW states for LoRA only
            
            per_gpu = (base_memory_gb / self.config.tensor_parallel + 
                      lora_memory_gb + optimizer_memory_gb)
        elif self.config.method == "full":
            # Full fine-tuning with ZeRO-3
            model_memory = params_billions * bytes_per_param["bf16"]  # 140 GB
            optimizer_memory = params_billions * 12  # AdamW: 12 bytes/param
            gradient_memory = params_billions * 2  # bf16 gradients
            
            total = model_memory + optimizer_memory + gradient_memory  # ~980 GB
            per_gpu = total / self.world_size  # ZeRO-3 shards everything
        
        return {
            "per_gpu_gb": per_gpu,
            "activation_memory_gb": self._estimate_activations(),
            "total_cluster_gb": per_gpu * self.world_size,
            "recommended_gpu": "A100-80GB" if per_gpu > 40 else "A100-40GB"
        }

    def setup_parallelism(self):
        """Configure hybrid parallelism strategy."""
        from deepspeed import init_distributed
        from transformers import AutoModelForCausalLM
        import deepspeed
        
        # DeepSpeed ZeRO-3 config for full fine-tuning
        ds_config = {
            "bf16": {"enabled": True},
            "zero_optimization": {
                "stage": 3,
                "offload_optimizer": {"device": "cpu"},  # if GPU memory tight
                "offload_param": {"device": "none"},
                "overlap_comm": True,
                "contiguous_gradients": True,
                "reduce_scatter": True,
            },
            "gradient_accumulation_steps": self.config.gradient_accumulation,
            "train_micro_batch_size_per_gpu": self.config.micro_batch_size,
            "gradient_clipping": 1.0,
            "steps_per_print": 10,
            "wall_clock_breakdown": True,
        }
        
        # For QLoRA approach
        if self.config.method == "qlora":
            from peft import get_peft_model, LoraConfig
            from transformers import BitsAndBytesConfig
            
            quant_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_use_double_quant=True,
            )
            
            model = AutoModelForCausalLM.from_pretrained(
                "meta-llama/Llama-2-70b-hf",
                quantization_config=quant_config,
                device_map="auto",  # auto-shard across GPUs
            )
            
            lora_config = LoraConfig(
                r=64, lora_alpha=128,
                target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                               "gate_proj", "up_proj", "down_proj"],
                lora_dropout=0.05,
                task_type="CAUSAL_LM"
            )
            model = get_peft_model(model, lora_config)
        
        return model, ds_config

    async def train_with_recovery(self, model, dataset):
        """Training loop with checkpointing and failure recovery."""
        checkpoint_dir = f"s3://checkpoints/{self.config.model_size}/"
        checkpoint_interval = 100  # steps
        
        # Resume from last checkpoint if exists
        start_step = 0
        if await self._checkpoint_exists(checkpoint_dir):
            start_step = await self._load_checkpoint(model, checkpoint_dir)
        
        for step in range(start_step, total_steps):
            try:
                loss = self._training_step(model, dataset, step)
                
                # Periodic checkpoint
                if step % checkpoint_interval == 0:
                    await self._save_checkpoint(model, step, checkpoint_dir)
                
                # Health monitoring
                if self._detect_loss_spike(loss, threshold=10.0):
                    await self._alert("Loss spike detected", step, loss)
                    # Rollback to last good checkpoint
                    await self._load_checkpoint(model, checkpoint_dir)
                    
            except torch.cuda.OutOfMemoryError:
                # Reduce batch size and retry
                self.config.micro_batch_size = max(1, self.config.micro_batch_size // 2)
                self.config.gradient_accumulation *= 2
                continue
                
            except RuntimeError as e:
                if "NCCL" in str(e):
                    # Communication failure: wait and retry
                    await asyncio.sleep(30)
                    init_process_group(backend="nccl")
                    await self._load_checkpoint(model, checkpoint_dir)
```

### Memory Optimization Comparison (70B model)

| Method | Memory/GPU | GPUs Needed | Quality | Training Speed |
|--------|-----------|-------------|---------|---------------|
| Full FT (ZeRO-3) | ~30 GB | 32x A100-80GB | Best | 1x |
| LoRA (r=64) | ~45 GB | 8x A100-80GB | 95-98% | 3x faster |
| QLoRA (4-bit + LoRA) | ~20 GB | 4x A100-80GB | 93-97% | 2x faster |
| Full FT + offload | ~40 GB | 16x A100-80GB | Best | 0.5x (slow) |

### Production Considerations
- **Preemption handling**: Use spot/preemptible instances (70% cheaper); checkpoint every 5min
- **Communication optimization**: Use NCCL with NVLink within node; InfiniBand between nodes
- **Data loading**: Pre-tokenize and shard dataset; async prefetch to GPU
- **Monitoring**: Track MFU (Model FLOPs Utilization); target >50% for efficiency
- **Cost estimation**: 70B QLoRA fine-tune ≈ $50-200; Full fine-tune ≈ $2000-5000

---

## Q115: Design an evaluation-driven training pipeline

### Problem
Training automatically stops when evaluation metrics plateau or degrade, with evaluation harness and decision logic.

### Architecture

```
┌────────────────────────────────────────────────────────────┐
│          Evaluation-Driven Training Pipeline                 │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌────────────────────────────────────────────────────┐    │
│  │              Training Loop                          │    │
│  │  ┌────────┐    ┌────────────┐    ┌─────────────┐  │    │
│  │  │ Train  │───▶│ Eval Every │───▶│ Decision    │  │    │
│  │  │ N steps│    │ K steps    │    │ Engine      │  │    │
│  │  └────────┘    └────────────┘    └─────────────┘  │    │
│  └────────────────────────────────────────────────────┘    │
│                              │                              │
│                    ┌─────────┴──────────┐                  │
│                    │                    │                   │
│                    ▼                    ▼                   │
│           ┌──────────────┐    ┌──────────────────┐        │
│           │  Continue    │    │  Stop & Select   │        │
│           │  Training    │    │  Best Checkpoint │        │
│           └──────────────┘    └──────────────────┘        │
│                                                            │
│  ┌────────────────────────────────────────────────────┐   │
│  │          Evaluation Harness                         │   │
│  │  ┌─────────┐ ┌──────────┐ ┌─────────┐ ┌────────┐ │   │
│  │  │Accuracy │ │Perplexity│ │ Domain  │ │Safety  │ │   │
│  │  │(exact)  │ │(loss)    │ │ Specific│ │Tests   │ │   │
│  │  └─────────┘ └──────────┘ └─────────┘ └────────┘ │   │
│  └────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────┘
```

### Implementation

```python
from dataclasses import dataclass, field
from typing import List, Callable
import numpy as np

@dataclass
class EvalMetric:
    name: str
    compute_fn: Callable
    higher_is_better: bool = True
    weight: float = 1.0
    min_acceptable: float = 0.0  # absolute floor

@dataclass
class StopDecision:
    should_stop: bool
    reason: str
    best_checkpoint_step: int
    metrics_history: dict

class EvaluationDrivenTrainer:
    def __init__(self, model, train_data, eval_config: dict):
        self.model = model
        self.train_data = train_data
        self.eval_interval = eval_config.get("eval_every_steps", 50)
        self.patience = eval_config.get("patience", 5)  # evals without improvement
        self.min_delta = eval_config.get("min_delta", 0.001)  # minimum improvement
        self.metrics_history = []
        self.best_score = -float('inf')
        self.best_step = 0
        self.patience_counter = 0

    def define_eval_harness(self) -> List[EvalMetric]:
        """Define comprehensive evaluation metrics."""
        return [
            EvalMetric("task_accuracy", self._eval_task_accuracy, weight=0.4),
            EvalMetric("perplexity", self._eval_perplexity, higher_is_better=False, weight=0.2),
            EvalMetric("domain_f1", self._eval_domain_specific, weight=0.2),
            EvalMetric("safety_score", self._eval_safety, weight=0.1, min_acceptable=0.95),
            EvalMetric("coherence", self._eval_coherence, weight=0.1),
        ]

    async def train(self) -> StopDecision:
        """Training loop with evaluation-driven stopping."""
        metrics_defs = self.define_eval_harness()
        
        for step in range(self.max_steps):
            # Training step
            loss = self._train_step(step)
            
            # Evaluate periodically
            if step > 0 and step % self.eval_interval == 0:
                eval_results = await self._run_evaluation(metrics_defs)
                self.metrics_history.append({"step": step, **eval_results})
                
                # Compute composite score
                composite = self._composite_score(eval_results, metrics_defs)
                
                # Decision logic
                decision = self._should_stop(composite, eval_results, metrics_defs, step)
                if decision.should_stop:
                    return decision
                
                # Update best
                if composite > self.best_score + self.min_delta:
                    self.best_score = composite
                    self.best_step = step
                    self.patience_counter = 0
                    self._save_checkpoint(step, tag="best")
                else:
                    self.patience_counter += 1

        return StopDecision(
            should_stop=True, reason="max_steps_reached",
            best_checkpoint_step=self.best_step,
            metrics_history=self.metrics_history
        )

    def _should_stop(self, composite: float, eval_results: dict,
                     metrics_defs: List[EvalMetric], step: int) -> StopDecision:
        """Multi-criteria stopping decision."""
        
        # Reason 1: Patience exhausted (plateau)
        if self.patience_counter >= self.patience:
            return StopDecision(True, "plateau_detected", self.best_step, self.metrics_history)
        
        # Reason 2: Critical metric below floor
        for metric in metrics_defs:
            if metric.min_acceptable > 0:
                value = eval_results[metric.name]
                if (metric.higher_is_better and value < metric.min_acceptable) or \
                   (not metric.higher_is_better and value > metric.min_acceptable):
                    if step > self.eval_interval * 3:  # give warmup
                        return StopDecision(True, f"{metric.name}_below_floor",
                                          self.best_step, self.metrics_history)
        
        # Reason 3: Overfitting detected (train loss dropping but eval degrading)
        if len(self.metrics_history) >= 3:
            recent = [m.get("perplexity", 0) for m in self.metrics_history[-3:]]
            if all(recent[i] > recent[i-1] for i in range(1, len(recent))):
                return StopDecision(True, "overfitting_detected",
                                  self.best_step, self.metrics_history)
        
        # Reason 4: Diminishing returns (slope near zero)
        if len(self.metrics_history) >= 5:
            scores = [self._composite_score(m, metrics_defs) 
                     for m in self.metrics_history[-5:]]
            slope = np.polyfit(range(5), scores, 1)[0]
            if abs(slope) < self.min_delta / 10:
                return StopDecision(True, "diminishing_returns",
                                  self.best_step, self.metrics_history)
        
        return StopDecision(False, "continue", self.best_step, self.metrics_history)

    def _composite_score(self, results: dict, metrics: List[EvalMetric]) -> float:
        """Weighted composite of all metrics (normalized to 0-1)."""
        score = 0
        for metric in metrics:
            value = results.get(metric.name, 0)
            normalized = value if metric.higher_is_better else (1 - value)
            score += metric.weight * normalized
        return score

    async def _run_evaluation(self, metrics: List[EvalMetric]) -> dict:
        """Run all evaluation metrics."""
        results = {}
        for metric in metrics:
            results[metric.name] = await metric.compute_fn(self.model)
        return results
```

### Stopping Criteria Decision Matrix

| Signal | Threshold | Action | Confidence |
|--------|-----------|--------|-----------|
| Plateau (patience=5) | <0.1% improvement for 5 evals | Stop, use best checkpoint | High |
| Overfitting | Eval loss increasing 3 evals in a row | Stop, use checkpoint before increase | High |
| Safety degradation | Safety score < 0.95 | Stop immediately | Critical |
| Diminishing returns | Slope < 0.0001 | Stop, cost not justified | Medium |
| Training instability | Loss spike > 10x | Rollback to last good checkpoint | High |

### Production Considerations
- **Eval cost**: Full evaluation is expensive; use subset (10%) for frequent evals, full set every 5th eval
- **Async evaluation**: Run eval on separate GPU while training continues on next batch
- **Multi-objective**: Track Pareto frontier; don't stop if one metric improves while others are stable
- **Human-in-the-loop**: Surface decision to human if confidence is low; show metrics dashboard
- **Checkpoint management**: Keep top-3 checkpoints; delete others to save storage
# Model Serving and Inference Optimization (Questions 116-120)

## Q116: Design model serving infrastructure with vLLM/TensorRT-LLM

### Problem
Maximize GPU utilization through continuous batching, PagedAttention, and KV-cache optimization for production LLM serving.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│            High-Performance Model Serving Infrastructure      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                 Load Balancer                          │   │
│  │  (request routing by estimated tokens, priority)      │   │
│  └──────────────────────────────────────────────────────┘   │
│                          │                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Inference Engine (vLLM)                   │   │
│  │                                                       │   │
│  │  ┌────────────────────────────────────────────────┐  │   │
│  │  │         Continuous Batching Scheduler            │  │   │
│  │  │  ┌─────────┐ ┌──────────┐ ┌──────────────┐    │  │   │
│  │  │  │ Waiting │ │ Running  │ │ Preempted    │    │  │   │
│  │  │  │ Queue   │ │ Batch    │ │ Queue        │    │  │   │
│  │  │  └─────────┘ └──────────┘ └──────────────┘    │  │   │
│  │  └────────────────────────────────────────────────┘  │   │
│  │                                                       │   │
│  │  ┌────────────────────────────────────────────────┐  │   │
│  │  │         PagedAttention KV-Cache Manager         │  │   │
│  │  │  ┌──────┐┌──────┐┌──────┐┌──────┐            │  │   │
│  │  │  │Page 0││Page 1││Page 2││ ...  │ (4KB each)  │  │   │
│  │  │  └──────┘└──────┘└──────┘└──────┘            │  │   │
│  │  │  Block Table: seq_id -> [page_ids]             │  │   │
│  │  └────────────────────────────────────────────────┘  │   │
│  │                                                       │   │
│  │  ┌────────────────────────────────────────────────┐  │   │
│  │  │         GPU Memory Layout                       │  │   │
│  │  │  [Model Weights 60%] [KV-Cache 35%] [Act. 5%] │  │   │
│  │  └────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Implementation

```python
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from enum import Enum
import asyncio

class RequestState(Enum):
    WAITING = "waiting"
    RUNNING = "running"
    PREEMPTED = "preempted"
    FINISHED = "finished"

@dataclass
class InferenceRequest:
    request_id: str
    prompt_tokens: List[int]
    max_new_tokens: int
    priority: int = 0
    arrival_time: float = 0
    state: RequestState = RequestState.WAITING
    generated_tokens: List[int] = field(default_factory=list)
    kv_cache_pages: List[int] = field(default_factory=list)

class ContinuousBatchingScheduler:
    """Iteration-level scheduling: add/remove requests every decode step."""
    
    def __init__(self, max_batch_size: int = 256, max_tokens_per_batch: int = 8192,
                 gpu_memory_gb: float = 80):
        self.max_batch_size = max_batch_size
        self.max_tokens = max_tokens_per_batch
        self.waiting_queue = []  # priority queue
        self.running_batch = []
        self.kv_cache_manager = PagedKVCacheManager(gpu_memory_gb)

    def schedule_step(self) -> List[InferenceRequest]:
        """Called every decode iteration to determine batch composition."""
        # 1. Remove finished sequences
        self.running_batch = [r for r in self.running_batch 
                             if r.state == RequestState.RUNNING]
        
        # 2. Try to add new requests from waiting queue
        while self.waiting_queue and self._can_add_request(self.waiting_queue[0]):
            request = self.waiting_queue.pop(0)
            # Allocate KV-cache pages
            pages = self.kv_cache_manager.allocate(request.prompt_tokens)
            if pages is None:
                # No memory: preempt lowest priority running request
                preempted = self._preempt_lowest_priority()
                if preempted:
                    pages = self.kv_cache_manager.allocate(request.prompt_tokens)
                else:
                    self.waiting_queue.insert(0, request)
                    break
            
            request.kv_cache_pages = pages
            request.state = RequestState.RUNNING
            self.running_batch.append(request)
        
        return self.running_batch

    def _can_add_request(self, request: InferenceRequest) -> bool:
        """Check if we can fit another request in the batch."""
        if len(self.running_batch) >= self.max_batch_size:
            return False
        current_tokens = sum(len(r.prompt_tokens) + len(r.generated_tokens) 
                           for r in self.running_batch)
        if current_tokens + len(request.prompt_tokens) > self.max_tokens:
            return False
        return self.kv_cache_manager.has_capacity(len(request.prompt_tokens))

    def _preempt_lowest_priority(self) -> Optional[InferenceRequest]:
        """Preempt request with lowest priority (swap KV-cache to CPU)."""
        if not self.running_batch:
            return None
        lowest = min(self.running_batch, key=lambda r: r.priority)
        self.kv_cache_manager.swap_out(lowest.kv_cache_pages)  # GPU -> CPU
        lowest.state = RequestState.PREEMPTED
        self.running_batch.remove(lowest)
        return lowest

class PagedKVCacheManager:
    """Manages KV-cache using paging (like OS virtual memory)."""
    
    def __init__(self, gpu_memory_gb: float, page_size: int = 16):
        # page_size = number of tokens per page
        self.page_size = page_size
        # Calculate available pages (assume 35% of GPU for KV-cache)
        kv_memory_bytes = int(gpu_memory_gb * 0.35 * 1e9)
        # Per-page memory: 2 (K+V) * num_layers * hidden_dim * 2 (bf16) * page_size
        self.bytes_per_page = 2 * 80 * 8192 * 2 * page_size  # ~40MB for 70B model
        self.total_pages = kv_memory_bytes // self.bytes_per_page
        self.free_pages = list(range(self.total_pages))
        self.page_table: Dict[str, List[int]] = {}  # seq_id -> page_ids

    def allocate(self, tokens: List[int]) -> Optional[List[int]]:
        """Allocate pages for a sequence."""
        pages_needed = (len(tokens) + self.page_size - 1) // self.page_size
        if len(self.free_pages) < pages_needed:
            return None
        allocated = [self.free_pages.pop() for _ in range(pages_needed)]
        return allocated

    def has_capacity(self, num_tokens: int) -> bool:
        pages_needed = (num_tokens + self.page_size - 1) // self.page_size
        return len(self.free_pages) >= pages_needed

    def free(self, pages: List[int]):
        """Return pages to free list."""
        self.free_pages.extend(pages)

    def swap_out(self, pages: List[int]):
        """Swap KV-cache pages from GPU to CPU (for preemption)."""
        # In practice: async cudaMemcpyAsync GPU->CPU
        pass

    def copy_on_write(self, pages: List[int]) -> List[int]:
        """For beam search / parallel sampling: share pages until write."""
        # Increment reference count; only copy page on modification
        return pages  # logical sharing, physical copy deferred
```

### Performance Metrics

| Metric | Without Optimization | With vLLM | Improvement |
|--------|---------------------|-----------|-------------|
| Throughput (tokens/s) | 500 | 2000+ | 4x |
| GPU utilization | 30-40% | 85-95% | 2.5x |
| Memory waste | 60-80% | <5% | 15x reduction |
| P50 latency (TTFT) | 2s | 200ms | 10x |
| Max concurrent requests | 8 | 256 | 32x |

### Production Considerations
- **Prefix caching**: Cache KV-cache for common system prompts; share across requests
- **Chunked prefill**: Process long prompts in chunks to avoid blocking decode steps
- **Priority queues**: Premium users get higher priority; preempt free-tier requests
- **Auto-scaling**: Scale GPU instances based on queue depth, not CPU utilization
- **Health checks**: Monitor KV-cache fragmentation; periodic compaction

---

## Q117: Design a speculative decoding system

### Problem
Use a small draft model to speed up a large target model by 2-3x while maintaining exact output distribution.

### Architecture

```
┌────────────────────────────────────────────────────────────┐
│              Speculative Decoding System                     │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Draft Phase (fast, small model)                     │   │
│  │                                                      │   │
│  │  Token 1 ──▶ Token 2 ──▶ Token 3 ──▶ ... Token K   │   │
│  │  (7B model, ~5ms per token)                          │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                  │
│                          ▼ (K draft tokens)                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Verification Phase (target model, single forward)   │   │
│  │                                                      │   │
│  │  ┌──────────────────────────────────────────────┐   │   │
│  │  │ Parallel verification of all K draft tokens   │   │   │
│  │  │ P_target(token_i | prefix + tokens_1..i-1)    │   │   │
│  │  └──────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                  │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Acceptance/Rejection (token by token)               │   │
│  │                                                      │   │
│  │  Token 1: ✓ Accept  (P_target >= P_draft)           │   │
│  │  Token 2: ✓ Accept                                  │   │
│  │  Token 3: ✗ Reject  → Resample from adjusted dist  │   │
│  │  Token 4+: Discard                                  │   │
│  │                                                      │   │
│  │  Result: 3 tokens from 1 target forward pass!       │   │
│  └─────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────┘
```

### Implementation

```python
import torch
import torch.nn.functional as F
from typing import Tuple, List

class SpeculativeDecoder:
    def __init__(self, target_model, draft_model, 
                 speculation_length: int = 5, temperature: float = 1.0):
        self.target = target_model  # 70B
        self.draft = draft_model    # 7B (same tokenizer)
        self.K = speculation_length
        self.temperature = temperature

    @torch.no_grad()
    def generate(self, input_ids: torch.Tensor, max_tokens: int) -> torch.Tensor:
        """Generate tokens using speculative decoding."""
        generated = input_ids.clone()
        tokens_generated = 0
        
        while tokens_generated < max_tokens:
            # Phase 1: Draft K tokens with small model
            draft_tokens, draft_probs = self._draft_phase(generated)
            
            # Phase 2: Verify all K tokens with target model in one forward pass
            target_probs = self._verify_phase(generated, draft_tokens)
            
            # Phase 3: Accept/reject using modified rejection sampling
            accepted, bonus_token = self._acceptance_phase(
                draft_tokens, draft_probs, target_probs
            )
            
            # Append accepted tokens + bonus token
            generated = torch.cat([generated, accepted, bonus_token.unsqueeze(0)], dim=-1)
            tokens_generated += len(accepted) + 1
            
            # Adaptive K: increase if acceptance rate high, decrease if low
            acceptance_rate = len(accepted) / self.K
            self.K = self._adapt_k(acceptance_rate)
        
        return generated[:, input_ids.shape[-1]:]  # return only new tokens

    def _draft_phase(self, prefix: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Generate K tokens with draft model."""
        draft_tokens = []
        draft_probs = []
        current = prefix
        
        for _ in range(self.K):
            logits = self.draft(current)[:, -1, :]
            probs = F.softmax(logits / self.temperature, dim=-1)
            token = torch.multinomial(probs, 1)
            draft_tokens.append(token.item())
            draft_probs.append(probs[0])
            current = torch.cat([current, token], dim=-1)
        
        return torch.tensor(draft_tokens), torch.stack(draft_probs)

    def _verify_phase(self, prefix: torch.Tensor, 
                      draft_tokens: torch.Tensor) -> torch.Tensor:
        """Single forward pass of target model on prefix + all draft tokens."""
        # Concatenate prefix with draft tokens
        full_sequence = torch.cat([prefix, draft_tokens.unsqueeze(0)], dim=-1)
        
        # One forward pass gives logits for all positions
        logits = self.target(full_sequence)
        
        # Extract probabilities for positions where we need to verify
        # Position i gives P(token at i+1 | tokens 0..i)
        start_pos = prefix.shape[-1] - 1
        target_logits = logits[:, start_pos:start_pos + self.K + 1, :]
        target_probs = F.softmax(target_logits / self.temperature, dim=-1)
        
        return target_probs[0]  # [K+1, vocab_size]

    def _acceptance_phase(self, draft_tokens: torch.Tensor,
                          draft_probs: torch.Tensor,
                          target_probs: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Modified rejection sampling preserving target distribution."""
        accepted = []
        
        for i in range(self.K):
            token = draft_tokens[i]
            p_draft = draft_probs[i, token]
            p_target = target_probs[i, token]
            
            # Accept with probability min(1, p_target / p_draft)
            acceptance_prob = min(1.0, (p_target / p_draft).item())
            
            if torch.rand(1).item() < acceptance_prob:
                accepted.append(token)
            else:
                # Reject: sample from adjusted distribution
                # P_adjusted = normalize(max(0, P_target - P_draft))
                adjusted = torch.clamp(target_probs[i] - draft_probs[i], min=0)
                adjusted = adjusted / adjusted.sum()
                bonus = torch.multinomial(adjusted, 1)
                return torch.tensor(accepted), bonus.squeeze()
        
        # All K tokens accepted! Sample bonus token from target at position K
        bonus = torch.multinomial(target_probs[self.K], 1)
        return torch.tensor(accepted), bonus.squeeze()

    def _adapt_k(self, acceptance_rate: float) -> int:
        """Dynamically adjust speculation length."""
        if acceptance_rate > 0.8:
            return min(self.K + 1, 10)  # speculate more
        elif acceptance_rate < 0.4:
            return max(self.K - 1, 2)  # speculate less
        return self.K
```

### When to Use / Not Use

| Scenario | Use Speculative Decoding? | Rationale |
|----------|--------------------------|-----------|
| High acceptance rate (>70%) | Yes | 2-3x speedup |
| Creative/high-temp generation | No | Low acceptance rate, wasted compute |
| Batch size > 1 | Depends | Less benefit (GPU already utilized) |
| Draft model unavailable | No | Need aligned draft model |
| Latency-critical (single user) | Yes | Best for reducing per-user latency |
| Throughput-critical (many users) | Maybe | Continuous batching might be better |

### Speedup Analysis

| Draft Model | Target Model | Acceptance Rate | Speedup | Overhead |
|-------------|-------------|-----------------|---------|----------|
| Llama-7B | Llama-70B | 75% | 2.5x | Draft GPU cost |
| 2-layer model | GPT-4 | 60% | 1.8x | Minimal |
| Medusa heads | Same model | 80% | 2.8x | +5% params |
| N-gram cache | Any | 40-90% (varies) | 1.5-3x | CPU only |

### Production Considerations
- **Draft model alignment**: Draft must share tokenizer; fine-tune on target's outputs for higher acceptance
- **Memory**: Need both models in GPU memory (or draft on CPU if small enough)
- **Adaptive K**: Monitor acceptance rate per-request; adjust dynamically
- **Batched verification**: Batch multiple sequences' verifications together
- **Fallback**: If acceptance rate drops below 30%, disable speculative decoding for that request

---

## Q118: Design a quantization strategy for production LLM deployment

### Problem
Select and deploy optimal quantization (GPTQ, AWQ, GGUF) based on hardware and quality requirements.

### Architecture

```
┌────────────────────────────────────────────────────────────────┐
│              Quantization Strategy Framework                     │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐    │
│  │                Quantization Selector                     │    │
│  │                                                         │    │
│  │  Input: model_size, hardware, quality_req, latency_req  │    │
│  │  Output: quantization_method + config                   │    │
│  └────────────────────────────────────────────────────────┘    │
│                          │                                      │
│          ┌───────────────┼───────────────┐                     │
│          ▼               ▼               ▼                     │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐           │
│  │    GPTQ      │ │    AWQ       │ │    GGUF      │           │
│  │  (GPU, 4bit) │ │ (GPU, 4bit) │ │ (CPU/GPU,    │           │
│  │  Post-train  │ │ Activation-  │ │  mixed quant)│           │
│  │  per-column  │ │ aware        │ │              │           │
│  └──────────────┘ └──────────────┘ └──────────────┘           │
│                          │                                      │
│                          ▼                                      │
│  ┌────────────────────────────────────────────────────────┐    │
│  │              Quality Validation Pipeline                 │    │
│  │  [Perplexity Check] [Task Accuracy] [Edge Cases]       │    │
│  └────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
from dataclasses import dataclass
from typing import Optional
from enum import Enum

class QuantMethod(Enum):
    FP16 = "fp16"
    GPTQ_4BIT = "gptq_4bit"
    GPTQ_8BIT = "gptq_8bit"
    AWQ_4BIT = "awq_4bit"
    GGUF_Q4_K_M = "gguf_q4_k_m"
    GGUF_Q5_K_M = "gguf_q5_k_m"
    GGUF_Q8_0 = "gguf_q8_0"

@dataclass
class HardwareProfile:
    gpu_type: Optional[str]  # "A100", "T4", "RTX4090", None (CPU only)
    gpu_memory_gb: float = 0
    cpu_memory_gb: float = 64
    has_tensor_cores: bool = False

@dataclass
class QualityRequirement:
    max_perplexity_increase: float = 0.5  # % increase over fp16
    min_task_accuracy: float = 0.95  # relative to fp16 baseline
    critical_domains: list = None  # domains where quality matters most

class QuantizationSelector:
    def __init__(self):
        self.benchmarks = self._load_benchmarks()

    def select(self, model_size_b: float, hardware: HardwareProfile,
               quality_req: QualityRequirement, target_latency_ms: float) -> dict:
        """Select optimal quantization strategy."""
        
        # Calculate memory requirements for each method
        candidates = []
        for method in QuantMethod:
            memory_gb = self._estimate_memory(model_size_b, method)
            fits_gpu = memory_gb <= hardware.gpu_memory_gb * 0.85  # 85% headroom
            
            if method.name.startswith("GGUF") and not hardware.gpu_type:
                fits_hardware = memory_gb <= hardware.cpu_memory_gb * 0.7
            elif hardware.gpu_type:
                fits_hardware = fits_gpu
            else:
                continue
            
            if not fits_hardware:
                continue
            
            # Check quality constraints
            quality_loss = self._get_quality_loss(model_size_b, method)
            if quality_loss > quality_req.max_perplexity_increase:
                continue
            
            # Estimate latency
            latency = self._estimate_latency(model_size_b, method, hardware)
            if latency > target_latency_ms:
                continue
            
            candidates.append({
                "method": method,
                "memory_gb": memory_gb,
                "quality_loss_pct": quality_loss,
                "estimated_latency_ms": latency,
                "throughput_tokens_per_sec": self._estimate_throughput(model_size_b, method, hardware)
            })
        
        if not candidates:
            raise ValueError("No quantization method meets all constraints")
        
        # Rank by: quality first, then throughput
        candidates.sort(key=lambda c: (c["quality_loss_pct"], -c["throughput_tokens_per_sec"]))
        return candidates[0]

    def _estimate_memory(self, model_size_b: float, method: QuantMethod) -> float:
        """Estimate GPU/CPU memory in GB."""
        bits_per_param = {
            QuantMethod.FP16: 16,
            QuantMethod.GPTQ_4BIT: 4.5,  # 4-bit + overhead
            QuantMethod.GPTQ_8BIT: 8.5,
            QuantMethod.AWQ_4BIT: 4.2,   # slightly less overhead
            QuantMethod.GGUF_Q4_K_M: 4.8,
            QuantMethod.GGUF_Q5_K_M: 5.5,
            QuantMethod.GGUF_Q8_0: 8.5,
        }
        return model_size_b * bits_per_param[method] / 8  # bytes -> GB

    def _get_quality_loss(self, model_size_b: float, method: QuantMethod) -> float:
        """Perplexity increase % based on benchmarks."""
        # Larger models lose less quality from quantization
        base_loss = {
            QuantMethod.FP16: 0,
            QuantMethod.GPTQ_4BIT: 1.5,
            QuantMethod.GPTQ_8BIT: 0.3,
            QuantMethod.AWQ_4BIT: 1.0,  # AWQ typically better than GPTQ
            QuantMethod.GGUF_Q4_K_M: 1.8,
            QuantMethod.GGUF_Q5_K_M: 0.8,
            QuantMethod.GGUF_Q8_0: 0.2,
        }
        # Larger models are more robust to quantization
        size_factor = max(0.5, 1.0 - (model_size_b - 7) * 0.02)
        return base_loss[method] * size_factor

    async def quantize_model(self, model_path: str, method: QuantMethod) -> str:
        """Quantize model using selected method."""
        if method in (QuantMethod.GPTQ_4BIT, QuantMethod.GPTQ_8BIT):
            from auto_gptq import AutoGPTQForCausalLM
            bits = 4 if "4BIT" in method.name else 8
            
            model = AutoGPTQForCausalLM.from_pretrained(model_path)
            model.quantize(
                calibration_data=self._load_calibration_data(),
                bits=bits,
                group_size=128,
                desc_act=True,  # better quality, slightly slower
            )
            output_path = f"{model_path}-gptq-{bits}bit"
            model.save_quantized(output_path)
            
        elif method == QuantMethod.AWQ_4BIT:
            from awq import AutoAWQForCausalLM
            model = AutoAWQForCausalLM.from_pretrained(model_path)
            model.quantize(
                calibration_data=self._load_calibration_data(),
                quant_config={"w_bit": 4, "q_group_size": 128, "version": "gemm"}
            )
            output_path = f"{model_path}-awq-4bit"
            model.save_quantized(output_path)
        
        return output_path
```

### Quantization Comparison Table

| Method | Bits | Memory (70B) | Quality Loss | Speed (A100) | Speed (T4) | Best For |
|--------|------|-------------|-------------|-------------|-----------|----------|
| FP16 | 16 | 140 GB | 0% | 1x (baseline) | N/A | Training |
| GPTQ-4bit | 4 | 35 GB | 1-2% | 1.8x | 1x | GPU inference |
| AWQ-4bit | 4 | 33 GB | 0.5-1.5% | 2.0x | 1.1x | GPU (best quality/speed) |
| GGUF Q4_K_M | ~4.8 | 40 GB | 1-2% | 1.5x | N/A | CPU + GPU offload |
| GGUF Q5_K_M | ~5.5 | 45 GB | 0.5-1% | 1.3x | N/A | CPU (quality focus) |
| GGUF Q8_0 | 8 | 70 GB | <0.5% | 1.1x | N/A | Near-lossless CPU |

### Production Considerations
- **Calibration data**: Use 128-512 representative samples from production traffic
- **Per-layer quantization**: Keep first/last layers in higher precision (they're most sensitive)
- **Validation pipeline**: Run full eval suite on quantized model before deployment
- **A/B test**: Serve quantized model to 10% traffic; compare quality metrics vs fp16
- **Hardware matching**: AWQ optimized for NVIDIA tensor cores; GGUF for Apple Silicon/CPU

---

## Q119: Design model sharding for a 180B parameter model

### Problem
Serve 180B parameter model across multiple GPUs using tensor, pipeline, and expert parallelism.

### Architecture

```
┌────────────────────────────────────────────────────────────────┐
│          180B Model Sharding Strategy                            │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Option A: Tensor Parallelism (TP=8, within one node)          │
│  ┌──────────────────────────────────────────────────────┐      │
│  │  Layer N:                                             │      │
│  │  ┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐  │      │
│  │  │GPU0││GPU1││GPU2││GPU3││GPU4││GPU5││GPU6││GPU7│  │      │
│  │  │ 1/8││ 1/8││ 1/8││ 1/8││ 1/8││ 1/8││ 1/8││ 1/8│  │      │
│  │  └────┘└────┘└────┘└────┘└────┘└────┘└────┘└────┘  │      │
│  │  All-reduce after each layer (NVLink: 600 GB/s)      │      │
│  └──────────────────────────────────────────────────────┘      │
│                                                                 │
│  Option B: Pipeline Parallelism (PP=4, across nodes)           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐         │
│  │  Node 0  │ │  Node 1  │ │  Node 2  │ │  Node 3  │         │
│  │Layer 0-23│▶│Layer24-47│▶│Layer48-71│▶│Layer72-95│         │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘         │
│  Micro-batching to hide pipeline bubbles                       │
│                                                                 │
│  Option C: Hybrid (TP=8 intra-node × PP=2 inter-node)         │
│  ┌──────────────────────┐  ┌──────────────────────┐           │
│  │   Node 0 (TP=8)      │  │   Node 1 (TP=8)      │           │
│  │   Layers 0-47        │─▶│   Layers 48-95       │           │
│  │   8 GPUs, NVLink     │  │   8 GPUs, NVLink     │           │
│  └──────────────────────┘  └──────────────────────┘           │
│  Inter-node: InfiniBand (400 Gb/s)                             │
│                                                                 │
│  Option D: Expert Parallelism (MoE models)                     │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  Router → Expert 0 (GPU0) | Expert 1 (GPU1) | ...      │    │
│  │  Each expert: subset of FFN weights                     │    │
│  │  Only top-K experts activated per token                 │    │
│  └────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
from dataclasses import dataclass
from typing import Tuple

@dataclass
class ModelSpec:
    total_params_b: float  # 180B
    num_layers: int  # 96
    hidden_dim: int  # 12288
    num_heads: int  # 96
    is_moe: bool = False
    num_experts: int = 1
    experts_per_token: int = 1

@dataclass
class ClusterSpec:
    num_nodes: int
    gpus_per_node: int
    gpu_memory_gb: float
    intra_node_bandwidth_gbps: float  # NVLink
    inter_node_bandwidth_gbps: float  # InfiniBand

class ShardingPlanner:
    def __init__(self, model: ModelSpec, cluster: ClusterSpec):
        self.model = model
        self.cluster = cluster
        self.total_gpus = cluster.num_nodes * cluster.gpus_per_node

    def plan(self) -> dict:
        """Determine optimal sharding strategy."""
        model_memory_gb = self.model.total_params_b * 2  # bf16
        per_gpu_memory = self.cluster.gpu_memory_gb * 0.80  # leave headroom
        
        # Minimum GPUs needed just for weights
        min_gpus = int(model_memory_gb / per_gpu_memory) + 1
        
        # Strategy selection
        if min_gpus <= self.cluster.gpus_per_node:
            # Fits in one node: use tensor parallelism only
            tp = min_gpus
            pp = 1
            strategy = "tensor_parallel_only"
        elif min_gpus <= self.total_gpus:
            # Multi-node: hybrid TP + PP
            tp = self.cluster.gpus_per_node  # max TP within node (fast NVLink)
            pp = (min_gpus + tp - 1) // tp  # pipeline stages across nodes
            strategy = "hybrid_tp_pp"
        else:
            raise ValueError(f"Model requires {min_gpus} GPUs, cluster has {self.total_gpus}")

        # For MoE models: expert parallelism
        if self.model.is_moe:
            ep = min(self.model.num_experts, self.total_gpus)
            strategy = "expert_parallel"
        else:
            ep = 1

        return {
            "strategy": strategy,
            "tensor_parallel": tp,
            "pipeline_parallel": pp,
            "expert_parallel": ep,
            "data_parallel": self.total_gpus // (tp * pp),
            "memory_per_gpu_gb": model_memory_gb / (tp * pp),
            "communication_overhead": self._estimate_comm_overhead(tp, pp),
            "pipeline_bubble_fraction": (pp - 1) / (pp - 1 + self._num_microbatches()),
        }

    def _estimate_comm_overhead(self, tp: int, pp: int) -> dict:
        """Estimate communication costs."""
        # TP: 2 all-reduces per layer (forward + backward)
        # Each all-reduce: 2 * (tp-1)/tp * hidden_dim * seq_len * 2 bytes
        tp_volume_per_layer = 2 * (tp - 1) / tp * self.model.hidden_dim * 4096 * 2
        tp_time_per_layer_us = tp_volume_per_layer / (self.cluster.intra_node_bandwidth_gbps * 1e9 / 8) * 1e6
        
        # PP: send activation between stages
        pp_volume = self.model.hidden_dim * 4096 * 2  # one activation tensor
        pp_time_us = pp_volume / (self.cluster.inter_node_bandwidth_gbps * 1e9 / 8) * 1e6
        
        return {
            "tp_overhead_per_layer_us": tp_time_per_layer_us,
            "pp_overhead_per_stage_us": pp_time_us,
            "total_comm_fraction": "~15-25% for TP=8, PP=2"
        }

    def _num_microbatches(self) -> int:
        """More microbatches = less pipeline bubble."""
        return 16  # typical: 4x pipeline stages
```

### Parallelism Trade-offs

| Strategy | Latency | Throughput | Communication | Complexity |
|----------|---------|-----------|---------------|-----------|
| TP only (8 GPU) | Lowest | Good | High (all-reduce every layer) | Low |
| PP only (4 stages) | Higher (bubbles) | Good | Low (point-to-point) | Medium |
| Hybrid TP+PP | Medium | Best | Medium | High |
| Expert Parallel (MoE) | Low (sparse) | Very High | Medium (all-to-all) | High |

### Production Considerations
- **Intra-node TP**: Always max out NVLink before going inter-node (10x faster than IB)
- **Pipeline bubbles**: Use 4x microbatches per pipeline stage to keep bubble <20%
- **Failure handling**: If one GPU fails in TP group, entire group must restart; PP can isolate failures
- **Load balancing (MoE)**: Monitor expert utilization; add auxiliary loss for balanced routing
- **Scaling inference**: For more throughput, add data parallelism replicas (each replica = full TP+PP group)

---

## Q120: Design KV-cache management for long-context applications (100K+ tokens)

### Problem
Manage KV-cache for 100K+ token contexts with eviction, compression, and multi-turn optimization.

### Architecture

```
┌────────────────────────────────────────────────────────────────┐
│           KV-Cache Management System (100K+ tokens)             │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐    │
│  │                 Tiered KV-Cache                          │    │
│  │                                                         │    │
│  │  ┌──────────────────────┐  Hot: Recent tokens           │    │
│  │  │   GPU HBM (fast)     │  (last 4K tokens)            │    │
│  │  │   ~20 GB             │  Full precision, instant      │    │
│  │  └──────────────────────┘                               │    │
│  │            │ evict                                       │    │
│  │            ▼                                             │    │
│  │  ┌──────────────────────┐  Warm: Important tokens       │    │
│  │  │   GPU HBM (compress) │  (attention-scored subset)    │    │
│  │  │   ~10 GB             │  Quantized (FP8/INT4)        │    │
│  │  └──────────────────────┘                               │    │
│  │            │ evict                                       │    │
│  │            ▼                                             │    │
│  │  ┌──────────────────────┐  Cold: Bulk context           │    │
│  │  │   CPU DRAM (swap)    │  (older context)             │    │
│  │  │   ~64 GB             │  Can reload on demand         │    │
│  │  └──────────────────────┘                               │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐    │
│  │          Multi-Turn Optimization                        │    │
│  │  Turn 1 KV ──┐                                         │    │
│  │  Turn 2 KV ──┼──▶ Shared prefix cache                  │    │
│  │  Turn 3 KV ──┘    (reuse across turns)                  │    │
│  └────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
import torch
from dataclasses import dataclass
from typing import Optional, List, Tuple
import numpy as np

@dataclass
class KVCacheConfig:
    max_seq_len: int = 131072  # 128K tokens
    num_layers: int = 80
    num_kv_heads: int = 8  # GQA
    head_dim: int = 128
    gpu_budget_gb: float = 30  # max GPU memory for KV-cache
    page_size: int = 256  # tokens per page

class TieredKVCacheManager:
    def __init__(self, config: KVCacheConfig):
        self.config = config
        self.hot_cache = {}      # GPU: recent tokens (full precision)
        self.warm_cache = {}     # GPU: important tokens (quantized)
        self.cold_cache = {}     # CPU: swapped out tokens
        
        # Calculate capacity per tier
        bytes_per_token = (2 * config.num_layers * config.num_kv_heads * 
                          config.head_dim * 2)  # K+V, bf16
        self.hot_capacity = int(config.gpu_budget_gb * 0.6 * 1e9 / bytes_per_token)
        self.warm_capacity = int(config.gpu_budget_gb * 0.3 * 1e9 / (bytes_per_token / 4))  # 4x compression
        
    def get_kv(self, seq_id: str, position: int) -> Tuple[torch.Tensor, torch.Tensor]:
        """Retrieve KV for a position, loading from appropriate tier."""
        if position in self.hot_cache.get(seq_id, {}):
            return self.hot_cache[seq_id][position]
        elif position in self.warm_cache.get(seq_id, {}):
            # Dequantize from warm cache
            return self._dequantize(self.warm_cache[seq_id][position])
        elif position in self.cold_cache.get(seq_id, {}):
            # Load from CPU to GPU
            kv = self.cold_cache[seq_id][position].cuda(non_blocking=True)
            return kv
        return None

    def append_kv(self, seq_id: str, position: int, k: torch.Tensor, v: torch.Tensor):
        """Add new KV entry, managing eviction."""
        if seq_id not in self.hot_cache:
            self.hot_cache[seq_id] = {}
        
        self.hot_cache[seq_id][position] = (k, v)
        
        # Eviction: if hot cache full, move old tokens based on policy
        if self._hot_cache_size(seq_id) > self.hot_capacity:
            self._evict(seq_id)

    def _evict(self, seq_id: str):
        """Eviction policy: keep recent + high-attention tokens."""
        cache = self.hot_cache[seq_id]
        positions = sorted(cache.keys())
        
        # Always keep last N tokens (recent window)
        recent_window = 2048
        protected = set(positions[-recent_window:])
        
        # Score remaining by attention importance (computed during forward pass)
        eviction_candidates = [p for p in positions if p not in protected]
        
        # Move bottom 50% to warm (quantized) or cold (CPU)
        to_evict = eviction_candidates[:len(eviction_candidates) // 2]
        
        for pos in to_evict:
            k, v = cache.pop(pos)
            if self._warm_has_capacity():
                # Quantize and store in warm tier
                self.warm_cache.setdefault(seq_id, {})[pos] = self._quantize(k, v)
            else:
                # Swap to CPU
                self.cold_cache.setdefault(seq_id, {})[pos] = (k.cpu(), v.cpu())

    def _quantize(self, k: torch.Tensor, v: torch.Tensor) -> dict:
        """Quantize KV to INT4 with per-channel scaling."""
        def quantize_tensor(t):
            scale = t.abs().max(dim=-1, keepdim=True).values / 7.0  # INT4 range
            quantized = torch.clamp(torch.round(t / scale), -8, 7).to(torch.int8)
            return {"data": quantized, "scale": scale.half()}
        return {"k": quantize_tensor(k), "v": quantize_tensor(v)}

    def _dequantize(self, quantized: dict) -> Tuple[torch.Tensor, torch.Tensor]:
        """Dequantize from INT4 back to bf16."""
        def dequant(q):
            return (q["data"].float() * q["scale"].float()).bfloat16()
        return dequant(quantized["k"]), dequant(quantized["v"])

class MultiTurnCacheOptimizer:
    """Optimize KV-cache for multi-turn conversations."""
    
    def __init__(self, kv_manager: TieredKVCacheManager):
        self.kv_manager = kv_manager
        self.prefix_cache = {}  # system_prompt_hash -> KV-cache

    def get_or_compute_prefix(self, system_prompt: str, model) -> dict:
        """Cache KV for system prompt; shared across all conversations."""
        prompt_hash = hash(system_prompt)
        if prompt_hash in self.prefix_cache:
            return self.prefix_cache[prompt_hash]
        
        # Compute KV for system prompt once
        kv = model.prefill(system_prompt)
        self.prefix_cache[prompt_hash] = kv
        return kv

    def new_turn(self, seq_id: str, turn_input: str, model):
        """Add new turn; reuse existing KV-cache for prior turns."""
        # KV-cache from previous turns is already stored
        # Just append new turn's tokens
        existing_len = self.kv_manager.get_seq_length(seq_id)
        new_kv = model.prefill(turn_input, kv_cache=self.kv_manager.get_all(seq_id))
        
        # Append new KV entries
        for pos, (k, v) in enumerate(new_kv, start=existing_len):
            self.kv_manager.append_kv(seq_id, pos, k, v)

    def summarize_and_compress(self, seq_id: str, model):
        """For very long conversations: summarize old turns, free KV-cache."""
        seq_len = self.kv_manager.get_seq_length(seq_id)
        if seq_len > 80000:  # compress when approaching limit
            # Keep last 20K tokens as-is
            # Summarize first 60K tokens into ~2K token summary
            old_text = model.decode_from_kv(self.kv_manager, seq_id, 0, 60000)
            summary = model.summarize(old_text, max_tokens=2000)
            
            # Replace old KV-cache with summary's KV-cache
            self.kv_manager.evict_range(seq_id, 0, 60000)
            summary_kv = model.prefill(summary)
            self.kv_manager.insert_at(seq_id, 0, summary_kv)
```

### KV-Cache Memory Calculator (per sequence)

| Model | Context | Precision | Memory/Sequence | 100 Concurrent |
|-------|---------|-----------|----------------|---------------|
| Llama 70B | 4K | bf16 | 2.5 GB | 250 GB |
| Llama 70B | 128K | bf16 | 80 GB | Impossible |
| Llama 70B | 128K | INT4 (warm) | 20 GB | 2 TB (distributed) |
| Llama 70B (GQA) | 128K | bf16 | 10 GB | 1 TB |

### Eviction Policy Comparison

| Policy | Quality Impact | Memory Savings | Complexity |
|--------|---------------|---------------|-----------|
| FIFO (oldest first) | Medium (loses important early context) | High | Low |
| Attention-scored | Low (keeps what model attends to) | High | Medium |
| Sliding window + sink | Low-Medium | Very High | Low |
| H2O (Heavy Hitter Oracle) | Very Low | High | Medium |
| Learned eviction | Lowest | High | High |

### Production Considerations
- **Prefix caching**: System prompts shared across users; cache once, reuse 1000x
- **Async prefetch**: Predict which cold pages will be needed; prefetch before decode step
- **GQA/MQA**: Use models with grouped-query attention (8 KV heads vs 64); 8x memory savings
- **Session affinity**: Route same user to same GPU to reuse their KV-cache
- **TTL**: Expire KV-cache after 30min idle; recompute on next message (cheaper than storing)
# Emerging AI Architectures (Questions 196-200)

## Q196: Design a Mixture of Experts (MoE) serving infrastructure. How do you efficiently serve a 400B MoE model where only 50B parameters are active per token? Include expert caching and routing optimization.

### Answer

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────────┐
│              MoE Serving Infrastructure (400B model)                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Request Flow                                                  │   │
│  │                                                                 │   │
│  │  Token → Router Network → Select Top-K Experts → Execute →     │   │
│  │          (learned gate)    (2 of 64 experts)    (sparse)       │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  GPU Cluster Layout (8 nodes × 8 GPUs = 64 GPUs)              │   │
│  │                                                                 │   │
│  │  ┌──────────────────────────────────────────────────────────┐ │   │
│  │  │ Expert Placement Strategy                                  │ │   │
│  │  │                                                            │ │   │
│  │  │ GPU 0-7:   Experts 0-7   (Node 1, NVLink)                │ │   │
│  │  │ GPU 8-15:  Experts 8-15  (Node 2, NVLink)                │ │   │
│  │  │ ...                                                        │ │   │
│  │  │ GPU 56-63: Experts 56-63 (Node 8, NVLink)                │ │   │
│  │  │                                                            │ │   │
│  │  │ Shared layers (attention, router) replicated on ALL GPUs   │ │   │
│  │  └──────────────────────────────────────────────────────────┘ │   │
│  │                                                                 │   │
│  │  ┌──────────────────────────────────────────────────────────┐ │   │
│  │  │ Expert Cache (Hot experts in GPU memory)                   │ │   │
│  │  │                                                            │ │   │
│  │  │ Popular experts: Always in GPU memory                      │ │   │
│  │  │ Warm experts: In CPU memory, prefetch on prediction        │ │   │
│  │  │ Cold experts: On SSD, load on demand                       │ │   │
│  │  └──────────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
import numpy as np
from collections import Counter

@dataclass
class MoEConfig:
    total_experts: int = 64
    active_experts_per_token: int = 2  # Top-K routing
    expert_size_gb: float = 6.25       # 400B / 64 experts
    shared_layers_gb: float = 20       # Attention + router
    gpu_memory_gb: float = 80          # A100-80GB
    num_gpus: int = 64

class ExpertCacheManager:
    """Manage expert weights across GPU/CPU/SSD hierarchy."""
    
    def __init__(self, config: MoEConfig):
        self.config = config
        # Budget: 80GB GPU - 20GB shared = 60GB for experts
        # Can fit ~9 experts per GPU in memory
        self.gpu_cache_capacity = int(
            (config.gpu_memory_gb - config.shared_layers_gb / config.num_gpus * 8) 
            / config.expert_size_gb
        )
        self.expert_access_counts = Counter()
        self.gpu_cache: Dict[int, List[int]] = {}  # gpu_id -> [expert_ids]
        self.cpu_cache: Dict[int, bytes] = {}
    
    def get_expert_placement(self) -> Dict[int, int]:
        """Determine which GPU holds which expert."""
        # Strategy: Place experts based on co-activation patterns
        # Experts often activated together should be on same node
        
        coactivation = self.compute_coactivation_matrix()
        
        # Greedy placement: assign co-activated experts to same GPU
        placement = {}
        assigned = set()
        
        for gpu_id in range(self.config.num_gpus):
            # Start with most popular unassigned expert
            candidates = [e for e in range(self.config.total_experts) if e not in assigned]
            if not candidates:
                break
            
            # Pick seed expert (most popular)
            seed = max(candidates, key=lambda e: self.expert_access_counts[e])
            placement[seed] = gpu_id
            assigned.add(seed)
            
            # Fill rest of GPU with co-activated experts
            for _ in range(self.gpu_cache_capacity - 1):
                remaining = [e for e in candidates if e not in assigned]
                if not remaining:
                    break
                # Pick expert most co-activated with seed
                best = max(remaining, key=lambda e: coactivation[seed][e])
                placement[best] = gpu_id
                assigned.add(best)
        
        return placement
    
    async def prefetch_experts(self, router_logits: np.ndarray):
        """Predict which experts will be needed and prefetch."""
        # Look at router logits for next tokens (speculative)
        top_k_experts = np.argsort(router_logits, axis=-1)[:, -4:]  # Top-4 (more than needed)
        
        for expert_id in np.unique(top_k_experts):
            if not self.is_in_gpu(expert_id):
                # Prefetch from CPU to GPU
                asyncio.create_task(self.load_to_gpu(expert_id))

class MoEServingEngine:
    """Efficient MoE inference with expert parallelism."""
    
    def __init__(self, config: MoEConfig, cache_manager: ExpertCacheManager):
        self.config = config
        self.cache = cache_manager
        self.placement = cache_manager.get_expert_placement()
    
    async def forward(self, tokens: np.ndarray) -> np.ndarray:
        """Forward pass through MoE model."""
        batch_size, seq_len = tokens.shape
        
        # 1. Run shared attention layers (replicated on all GPUs)
        hidden_states = await self.run_attention(tokens)
        
        # 2. Router: determine expert assignment
        router_logits = await self.run_router(hidden_states)
        expert_assignments = self.top_k_routing(router_logits)
        
        # 3. Dispatch tokens to experts (expert parallelism)
        expert_outputs = await self.dispatch_to_experts(
            hidden_states, expert_assignments
        )
        
        # 4. Combine expert outputs (weighted by router probability)
        output = self.combine_expert_outputs(
            expert_outputs, expert_assignments, router_logits
        )
        
        return output
    
    def top_k_routing(self, logits: np.ndarray) -> List[Tuple[int, float]]:
        """Route each token to top-K experts with load balancing."""
        k = self.config.active_experts_per_token
        
        # Apply load balancing (prevent expert collapse)
        balanced_logits = self.apply_load_balancing(logits)
        
        # Select top-K per token
        top_k_indices = np.argsort(balanced_logits, axis=-1)[:, -k:]
        top_k_probs = np.take_along_axis(
            self.softmax(balanced_logits), top_k_indices, axis=-1
        )
        
        return list(zip(top_k_indices, top_k_probs))
    
    async def dispatch_to_experts(self, hidden_states, assignments):
        """All-to-all communication to send tokens to expert GPUs."""
        # Group tokens by assigned expert
        expert_batches = {}
        for token_idx, (expert_ids, _) in enumerate(assignments):
            for eid in expert_ids:
                expert_batches.setdefault(eid, []).append(token_idx)
        
        # Send to appropriate GPUs (all-to-all)
        results = {}
        tasks = []
        for expert_id, token_indices in expert_batches.items():
            gpu_id = self.placement[expert_id]
            task = self.execute_expert_on_gpu(
                gpu_id, expert_id, 
                hidden_states[token_indices]
            )
            tasks.append((expert_id, task))
        
        # Execute all experts in parallel
        for expert_id, task in tasks:
            results[expert_id] = await task
        
        return results
    
    def apply_load_balancing(self, logits: np.ndarray) -> np.ndarray:
        """Prevent expert collapse (all tokens going to same expert)."""
        # Auxiliary loss: encourage uniform expert utilization
        # Add noise to prevent deterministic routing
        noise = np.random.gumbel(size=logits.shape) * 0.1
        return logits + noise
```

**Expert Caching Strategy:**

| Tier | Location | Capacity | Latency | Strategy |
|------|----------|----------|---------|----------|
| Hot | GPU HBM | ~9 experts/GPU | 0ms | Always resident (popular experts) |
| Warm | CPU RAM | All 64 experts | 5-10ms | Prefetch on router prediction |
| Cold | NVMe SSD | Archive | 50-100ms | Rarely activated experts |

**Performance Optimization:**

| Technique | Benefit | Tradeoff |
|-----------|---------|----------|
| Expert parallelism | All active experts run simultaneously | Communication overhead |
| Speculative prefetch | Hide expert loading latency | Wastes bandwidth on misprediction |
| Co-location by activation | Reduces cross-node communication | Less flexible scaling |
| Capacity factor | Limits per-expert batch size | May drop tokens |
| Expert merging | Reduce cold experts | Slight quality loss |

**Production Considerations:**
- **Load balancing**: Without balancing, 90% of tokens may route to 10% of experts (expert collapse)
- **Communication overhead**: All-to-all dispatch is the bottleneck; minimize cross-node transfers
- **Batch efficiency**: Larger batches amortize routing overhead; batch tokens across requests
- **Cost**: Only 50B of 400B active per token; serving cost similar to a 50B dense model
- **Monitoring**: Track per-expert utilization; alert on imbalanced routing

---

## Q197: Design a retrieval-augmented fine-tuning (RAFT) system that combines the benefits of RAG and fine-tuning. Include the training pipeline and inference architecture.

### Answer

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│              RAFT (Retrieval-Augmented Fine-Tuning)               │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  Training Pipeline                                           ││
│  │                                                               ││
│  │  Documents → Generate Q&A → Add Retrieved Context →          ││
│  │              (with oracle   (mix of relevant +               ││
│  │               + distractor   distractor docs)                ││
│  │               docs)                                          ││
│  │           → Fine-tune model to answer from context           ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  Inference                                                   ││
│  │                                                               ││
│  │  Query → Retrieve → Fine-tuned Model → Answer               ││
│  │          (same retriever    (trained to                      ││
│  │           as training)       extract from                    ││
│  │                              noisy context)                  ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                   │
│  Key Insight: Model learns to IGNORE distractors and             │
│  extract answers from relevant docs in retrieved context         │
└─────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass, field
from typing import List, Dict, Tuple
import random

@dataclass
class RAFTConfig:
    # Training data generation
    num_qa_per_document: int = 5
    num_distractor_docs: int = 3     # Non-relevant docs in context
    oracle_doc_ratio: float = 0.8    # 80% of time include oracle doc
    
    # Fine-tuning
    base_model: str = "llama-3-8b"
    learning_rate: float = 2e-5
    epochs: int = 3
    max_context_length: int = 4096
    
    # Chain-of-thought
    include_cot: bool = True  # Train model to cite sources

class RAFTTrainingPipeline:
    """Generate RAFT training data and fine-tune."""
    
    def __init__(self, config: RAFTConfig, llm, retriever, documents):
        self.config = config
        self.llm = llm
        self.retriever = retriever
        self.documents = documents
    
    async def generate_training_data(self) -> List[dict]:
        """Generate Q&A pairs with retrieval context (oracle + distractors)."""
        training_examples = []
        
        for doc in self.documents:
            # Generate questions answerable from this document
            qa_pairs = await self.generate_qa_pairs(doc)
            
            for question, answer in qa_pairs:
                # Create training example with context
                example = await self.create_training_example(
                    question, answer, oracle_doc=doc
                )
                training_examples.append(example)
        
        return training_examples
    
    async def create_training_example(self, question: str, answer: str,
                                       oracle_doc: dict) -> dict:
        """Create single training example with oracle + distractor docs."""
        
        # Get distractor documents (retrieved but not relevant)
        distractors = await self.get_distractors(question, oracle_doc)
        
        # Decide whether to include oracle doc (train robustness)
        include_oracle = random.random() < self.config.oracle_doc_ratio
        
        if include_oracle:
            # Mix oracle with distractors
            context_docs = distractors + [oracle_doc]
            random.shuffle(context_docs)
        else:
            # Only distractors (model should say "cannot answer")
            context_docs = distractors
            answer = "The provided context does not contain enough information to answer this question."
        
        # Format context
        context = self.format_context(context_docs)
        
        # Generate chain-of-thought answer
        if self.config.include_cot and include_oracle:
            cot_answer = await self.generate_cot_answer(question, answer, oracle_doc)
        else:
            cot_answer = answer
        
        return {
            "instruction": f"Answer the following question using ONLY the provided context. "
                          f"Cite the relevant document.\n\nContext:\n{context}\n\n"
                          f"Question: {question}",
            "output": cot_answer,
            "metadata": {
                "oracle_included": include_oracle,
                "num_distractors": len(distractors),
                "source_doc_id": oracle_doc["id"]
            }
        }
    
    async def get_distractors(self, question: str, oracle_doc: dict) -> List[dict]:
        """Get plausible but non-relevant documents."""
        # Retrieve documents similar to query but NOT the oracle
        retrieved = await self.retriever.retrieve(question, top_k=10)
        
        distractors = [
            doc for doc in retrieved 
            if doc["id"] != oracle_doc["id"]
        ][:self.config.num_distractor_docs]
        
        return distractors
    
    async def generate_cot_answer(self, question: str, answer: str, 
                                   oracle_doc: dict) -> str:
        """Generate chain-of-thought that cites sources."""
        return (
            f"Based on the context provided, specifically from document "
            f"'{oracle_doc.get('title', 'untitled')}': {answer}\n\n"
            f"##begin_quote##\n{self.extract_evidence(oracle_doc, answer)}\n##end_quote##"
        )
    
    async def fine_tune(self, training_data: List[dict]) -> str:
        """Fine-tune base model on RAFT data."""
        # Format for instruction tuning
        formatted = self.format_for_sft(training_data)
        
        # Fine-tune with LoRA for efficiency
        model_path = await self.trainer.train(
            base_model=self.config.base_model,
            training_data=formatted,
            method="lora",
            lora_config={"r": 16, "alpha": 32, "target_modules": ["q_proj", "v_proj"]},
            learning_rate=self.config.learning_rate,
            epochs=self.config.epochs
        )
        
        return model_path

class RAFTInferenceEngine:
    """Inference with RAFT fine-tuned model."""
    
    def __init__(self, model, retriever):
        self.model = model      # RAFT fine-tuned model
        self.retriever = retriever  # Same retriever used during training
    
    async def query(self, question: str, top_k: int = 5) -> dict:
        """RAG inference with RAFT model."""
        # 1. Retrieve (same retriever as training)
        retrieved_docs = await self.retriever.retrieve(question, top_k=top_k)
        
        # 2. Format context (same format as training)
        context = self.format_context(retrieved_docs)
        
        # 3. Generate with fine-tuned model
        prompt = (
            f"Answer the following question using ONLY the provided context. "
            f"Cite the relevant document.\n\nContext:\n{context}\n\n"
            f"Question: {question}\n\nAnswer:"
        )
        
        response = await self.model.generate(prompt, max_tokens=500)
        
        # 4. Extract citations
        citations = self.extract_citations(response)
        
        return {
            "answer": response,
            "citations": citations,
            "retrieved_docs": retrieved_docs
        }
```

**RAFT vs RAG vs Fine-tuning:**

| Aspect | Pure RAG | Pure Fine-tuning | RAFT |
|--------|----------|-----------------|------|
| Handles new docs | Yes (just add to index) | No (retrain needed) | Yes (retriever finds them) |
| Domain accuracy | Good | Best | Better than RAG |
| Hallucination | Medium | High | Low (trained to cite) |
| Distractor robustness | Poor | N/A | Excellent (trained on distractors) |
| Cost | Low (no training) | High (full FT) | Medium (LoRA FT) |
| Update frequency | Real-time | Periodic retrain | Periodic FT + real-time retrieval |

**Production Considerations:**
- **Training data quality**: Q&A generation quality determines RAFT effectiveness; use GPT-4 for generation
- **Retriever alignment**: MUST use same retriever at training and inference; mismatch degrades quality
- **Periodic retraining**: Re-run RAFT pipeline when corpus changes significantly (monthly)
- **Distractor ratio**: 80% oracle + distractors, 20% distractors-only trains robustness
- **Evaluation**: Compare RAFT model vs base RAG on held-out questions; expect 10-20% improvement

---

## Q198: Design a constitutional AI system where the model self-critiques and revises its outputs based on a set of principles. Include the critique-revision loop and production integration.

### Answer

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│              Constitutional AI System                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  Constitution (Principles)                                   ││
│  │  1. Be helpful and accurate                                  ││
│  │  2. Avoid harmful content                                    ││
│  │  3. Respect privacy                                          ││
│  │  4. Acknowledge uncertainty                                  ││
│  │  5. Be fair and unbiased                                     ││
│  │  ... (domain-specific principles)                            ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  Critique-Revision Loop                                      ││
│  │                                                               ││
│  │  Query → Generate Draft → Critique Against Principles →      ││
│  │                            ↓                                  ││
│  │                    Violations Found?                           ││
│  │                    ├── Yes → Revise → Re-critique (max 3x)    ││
│  │                    └── No → Return Response                   ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum

@dataclass
class Principle:
    id: str
    name: str
    description: str
    critique_prompt: str
    severity: str  # "critical", "important", "preferred"
    examples: List[dict] = field(default_factory=list)

@dataclass
class Critique:
    principle_id: str
    violated: bool
    explanation: str
    severity: str
    suggested_revision: Optional[str] = None

class ConstitutionalAI:
    """Self-critique and revise outputs based on principles."""
    
    def __init__(self, generator_llm, critic_llm, principles: List[Principle]):
        self.generator = generator_llm
        self.critic = critic_llm
        self.principles = principles
        self.max_revisions = 3
    
    async def generate(self, query: str, context: str = "") -> dict:
        """Generate response with constitutional self-critique."""
        
        # Step 1: Generate initial draft
        draft = await self.generator.generate(
            self.build_generation_prompt(query, context)
        )
        
        # Step 2: Critique-revision loop
        current_response = draft
        revision_history = [{"version": 0, "text": draft, "critiques": []}]
        
        for revision_num in range(self.max_revisions):
            # Critique against all principles
            critiques = await self.critique(query, current_response)
            
            # Check if any critical violations
            violations = [c for c in critiques if c.violated]
            
            revision_history[-1]["critiques"] = [c.__dict__ for c in critiques]
            
            if not violations:
                break  # Response passes all principles
            
            # Only revise for critical/important violations
            actionable = [c for c in violations if c.severity in ("critical", "important")]
            
            if not actionable:
                break  # Only "preferred" violations, acceptable
            
            # Revise
            current_response = await self.revise(
                query, current_response, actionable
            )
            
            revision_history.append({
                "version": revision_num + 1,
                "text": current_response,
                "critiques": []
            })
        
        return {
            "response": current_response,
            "revisions": len(revision_history) - 1,
            "history": revision_history,
            "final_critiques": critiques
        }
    
    async def critique(self, query: str, response: str) -> List[Critique]:
        """Critique response against all constitutional principles."""
        critiques = []
        
        # Batch critique (all principles at once for efficiency)
        principles_text = "\n".join(
            f"{p.id}. {p.name}: {p.description}" for p in self.principles
        )
        
        critique_prompt = f"""Review this response against the following principles.
For each violated principle, explain the violation and suggest a fix.

Principles:
{principles_text}

User Query: {query}
Response: {response}

For each principle, respond with:
- Principle ID
- Violated: yes/no
- Explanation (if violated)
- Suggested revision (if violated)

Output as JSON array."""
        
        result = await self.critic.generate(critique_prompt, temperature=0.0)
        critiques = self.parse_critiques(result)
        
        return critiques
    
    async def revise(self, query: str, response: str, 
                     violations: List[Critique]) -> str:
        """Revise response to address principle violations."""
        
        violations_text = "\n".join(
            f"- {v.principle_id}: {v.explanation}. Suggestion: {v.suggested_revision}"
            for v in violations
        )
        
        revision_prompt = f"""Revise the following response to address the identified issues,
while maintaining helpfulness and accuracy.

Original query: {query}
Original response: {response}

Issues to fix:
{violations_text}

Revised response:"""
        
        revised = await self.generator.generate(revision_prompt)
        return revised

class ConstitutionalAIProduction:
    """Production integration with caching and optimization."""
    
    def __init__(self, constitutional_ai, cache, config):
        self.cai = constitutional_ai
        self.cache = cache
        self.config = config
    
    async def serve(self, query: str, context: str = "") -> dict:
        """Production serving with latency optimization."""
        
        # Optimization 1: Skip critique for simple/cached queries
        if self.is_simple_query(query):
            return await self.cai.generator.generate(
                self.cai.build_generation_prompt(query, context)
            )
        
        # Optimization 2: Parallel critique (check multiple principles simultaneously)
        draft = await self.cai.generator.generate(
            self.cai.build_generation_prompt(query, context)
        )
        
        # Optimization 3: Lightweight pre-filter before full critique
        if not self.needs_full_critique(draft):
            return {"response": draft, "revisions": 0}
        
        # Full constitutional process
        return await self.cai.generate(query, context)
    
    def needs_full_critique(self, response: str) -> bool:
        """Fast heuristic check if critique is needed."""
        # Check for obvious red flags (regex/keyword based, <1ms)
        red_flags = [
            self.contains_sensitive_topics(response),
            self.contains_strong_claims(response),
            self.contains_instructions(response),
            len(response) > 2000,  # Long responses more likely to have issues
        ]
        return any(red_flags)
```

**Constitution Example (Enterprise AI):**

| Principle | Severity | Example Violation |
|-----------|----------|-------------------|
| Accuracy: Don't hallucinate | Critical | Citing non-existent sources |
| Privacy: No PII in responses | Critical | Including customer names/emails |
| Fairness: No bias | Important | Gender-biased recommendations |
| Uncertainty: Acknowledge limits | Important | Stating guesses as facts |
| Helpfulness: Answer the question | Preferred | Evasive non-answers |
| Conciseness: Don't ramble | Preferred | Unnecessary verbose responses |

**Production Considerations:**
- **Latency**: Critique loop adds 2-5s; use lightweight pre-filter to skip for safe responses (80% skip)
- **Cost**: Each revision = additional LLM call; cap at 3 revisions max
- **Separate models**: Use cheaper/faster model for critique, main model for generation
- **Principle versioning**: Constitution evolves; version principles and track which version produced each response
- **Monitoring**: Track revision rate, most-violated principles, and false positive critiques

---

## Q199: Design a multi-modal AI system (text + image + audio + video) with shared understanding. Include the embedding alignment, cross-modal retrieval, and unified generation architecture.

### Answer

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────────┐
│              Multi-Modal AI System                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Modal Encoders (Modality-Specific)                            │   │
│  │                                                                 │   │
│  │  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐             │   │
│  │  │ Text   │  │ Image  │  │ Audio  │  │ Video  │             │   │
│  │  │Encoder │  │Encoder │  │Encoder │  │Encoder │             │   │
│  │  │(BERT)  │  │(ViT)   │  │(Whisper│  │(ViViT) │             │   │
│  │  └───┬────┘  └───┬────┘  └───┬────┘  └───┬────┘             │   │
│  │      └────────────┴──────────┴────────────┘                   │   │
│  │                        │                                       │   │
│  │              ┌─────────▼──────────┐                           │   │
│  │              │  Alignment Layer   │                           │   │
│  │              │  (Shared Embedding │                           │   │
│  │              │   Space)           │                           │   │
│  │              └─────────┬──────────┘                           │   │
│  └────────────────────────┼──────────────────────────────────────┘   │
│                            │                                          │
│  ┌─────────────────────────▼──────────────────────────────────────┐  │
│  │  Unified Vector Index                                           │  │
│  │  (All modalities in same embedding space)                       │  │
│  │  Text query → finds relevant images, audio, video, text         │  │
│  └─────────────────────────┬──────────────────────────────────────┘  │
│                            │                                          │
│  ┌─────────────────────────▼──────────────────────────────────────┐  │
│  │  Multi-Modal Generator (GPT-4V / Gemini style)                  │  │
│  │  Accepts any modality input → generates text (+ image if needed)│  │
│  └─────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Union
from enum import Enum
import numpy as np

class Modality(Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"

@dataclass
class MultiModalDocument:
    id: str
    modality: Modality
    content: Union[str, bytes]
    aligned_embedding: List[float]  # In shared space
    metadata: dict = field(default_factory=dict)
    transcription: Optional[str] = None  # For audio/video

class MultiModalEmbedder:
    """Embed any modality into shared vector space."""
    
    def __init__(self):
        self.text_encoder = self.load_text_encoder()    # E.g., CLIP text
        self.image_encoder = self.load_image_encoder()  # E.g., CLIP vision
        self.audio_encoder = self.load_audio_encoder()  # E.g., CLAP
        self.video_encoder = self.load_video_encoder()  # E.g., VideoCLIP
        
        # Alignment projections (learned)
        self.projections = {
            Modality.TEXT: self.load_projection("text"),
            Modality.IMAGE: self.load_projection("image"),
            Modality.AUDIO: self.load_projection("audio"),
            Modality.VIDEO: self.load_projection("video"),
        }
    
    async def embed(self, content: Union[str, bytes], modality: Modality) -> List[float]:
        """Embed any modality into shared space."""
        
        # Get modality-specific embedding
        if modality == Modality.TEXT:
            raw_embedding = self.text_encoder.encode(content)
        elif modality == Modality.IMAGE:
            raw_embedding = self.image_encoder.encode(content)
        elif modality == Modality.AUDIO:
            raw_embedding = self.audio_encoder.encode(content)
        elif modality == Modality.VIDEO:
            raw_embedding = self.video_encoder.encode(content)
        
        # Project into shared alignment space
        aligned = self.projections[modality](raw_embedding)
        
        # Normalize
        aligned = aligned / np.linalg.norm(aligned)
        
        return aligned.tolist()

class CrossModalRetriever:
    """Retrieve across modalities in unified space."""
    
    def __init__(self, vector_store, embedder: MultiModalEmbedder):
        self.store = vector_store
        self.embedder = embedder
    
    async def retrieve(self, query: Union[str, bytes], 
                       query_modality: Modality,
                       target_modalities: List[Modality] = None,
                       top_k: int = 10) -> List[MultiModalDocument]:
        """Cross-modal retrieval: query in any modality, retrieve any modality."""
        
        # Embed query into shared space
        query_embedding = await self.embedder.embed(query, query_modality)
        
        # Search across all modalities (or filtered)
        filters = {}
        if target_modalities:
            filters["modality"] = {"$in": [m.value for m in target_modalities]}
        
        results = await self.store.query(
            vector=query_embedding,
            top_k=top_k,
            filter=filters
        )
        
        return results
    
    async def multi_modal_query(self, inputs: Dict[Modality, Union[str, bytes]],
                                 top_k: int = 10) -> List[MultiModalDocument]:
        """Query with multiple modalities simultaneously (fusion)."""
        
        # Embed each input modality
        embeddings = []
        for modality, content in inputs.items():
            emb = await self.embedder.embed(content, modality)
            embeddings.append(np.array(emb))
        
        # Fuse embeddings (simple average or learned fusion)
        fused = np.mean(embeddings, axis=0)
        fused = fused / np.linalg.norm(fused)
        
        return await self.store.query(vector=fused.tolist(), top_k=top_k)

class MultiModalRAG:
    """RAG system that handles multi-modal inputs and retrieval."""
    
    def __init__(self, retriever: CrossModalRetriever, generator):
        self.retriever = retriever
        self.generator = generator  # Multi-modal LLM (GPT-4V, Gemini)
    
    async def query(self, text_query: str, 
                    image_query: bytes = None,
                    audio_query: bytes = None) -> dict:
        """Multi-modal RAG query."""
        
        # 1. Build query from all input modalities
        inputs = {Modality.TEXT: text_query}
        if image_query:
            inputs[Modality.IMAGE] = image_query
        if audio_query:
            inputs[Modality.AUDIO] = audio_query
        
        # 2. Retrieve across all modalities
        results = await self.retriever.multi_modal_query(inputs, top_k=10)
        
        # 3. Prepare multi-modal context for generator
        context = self.prepare_multimodal_context(results)
        
        # 4. Generate with multi-modal LLM
        response = await self.generator.generate(
            text=text_query,
            images=[r.content for r in results if r.modality == Modality.IMAGE][:3],
            context=context
        )
        
        return {
            "response": response,
            "sources": [{"id": r.id, "modality": r.modality.value} for r in results]
        }
    
    def prepare_multimodal_context(self, results: List[MultiModalDocument]) -> str:
        """Prepare retrieved results as context for generator."""
        context_parts = []
        
        for r in results:
            if r.modality == Modality.TEXT:
                context_parts.append(f"[Text Document]: {r.content}")
            elif r.modality == Modality.IMAGE:
                context_parts.append(f"[Image]: {r.metadata.get('caption', 'No caption')}")
            elif r.modality == Modality.AUDIO:
                context_parts.append(f"[Audio Transcript]: {r.transcription}")
            elif r.modality == Modality.VIDEO:
                context_parts.append(f"[Video Transcript]: {r.transcription}")
        
        return "\n\n".join(context_parts)
```

**Embedding Alignment Approaches:**

| Approach | Method | Quality | Training Cost |
|----------|--------|---------|---------------|
| CLIP-style contrastive | Image-text pairs, contrastive loss | Good for image+text | High |
| ImageBind | One anchor modality (images), align all others | Good for 6 modalities | Very high |
| Projection heads | Pre-trained encoders + learned projection | Fast to train | Low |
| Joint training | Train all encoders together | Best alignment | Extremely high |

**Production Considerations:**
- **Modality gap**: Even in "shared" space, same-modality similarity > cross-modal; calibrate thresholds
- **Transcription**: Audio/video should be transcribed AND embedded; text retrieval often better than audio embedding
- **Storage**: Videos are large; store embeddings of keyframes + transcript, not full video
- **Latency**: Image/video encoding is slower; pre-compute embeddings at indexing time
- **Evaluation**: Cross-modal retrieval is harder to evaluate; need modality-specific and cross-modal benchmarks

---

## Q200: Design a real-time AI system that processes streaming data (IoT, market data, social media) and provides instant insights using RAG over both historical knowledge and live streams.

### Answer

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────────┐
│         Real-Time Streaming AI with Historical + Live RAG            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Streaming Ingestion                                           │   │
│  │  ┌────────┐  ┌────────┐  ┌───────────┐                       │   │
│  │  │ IoT    │  │ Market │  │ Social    │  → Kafka / Kinesis    │   │
│  │  │ Sensors│  │ Feeds  │  │ Media     │                       │   │
│  │  └────────┘  └────────┘  └───────────┘                       │   │
│  └──────────────────────────┬───────────────────────────────────┘   │
│                              │                                        │
│  ┌───────────────────────────▼──────────────────────────────────┐   │
│  │  Stream Processor (Flink / Kafka Streams)                     │   │
│  │                                                                │   │
│  │  ┌───────────────┐  ┌────────────────┐  ┌─────────────────┐ │   │
│  │  │ Window        │  │ Pattern        │  │ Real-Time       │ │   │
│  │  │ Aggregation   │  │ Detection      │  │ Embedding       │ │   │
│  │  │ (tumbling/    │  │ (anomalies,    │  │ + Index Update  │ │   │
│  │  │  sliding)     │  │  trends)       │  │                 │ │   │
│  │  └───────────────┘  └────────────────┘  └─────────────────┘ │   │
│  └──────────────────────────┬───────────────────────────────────┘   │
│                              │                                        │
│  ┌───────────────────────────▼──────────────────────────────────┐   │
│  │  Dual-Index RAG                                               │   │
│  │                                                                │   │
│  │  ┌────────────────────┐    ┌────────────────────────────┐    │   │
│  │  │ Historical Index   │    │ Live Index (Last N minutes)│    │   │
│  │  │ (Documents, past   │    │ (Streaming events,         │    │   │
│  │  │  events, knowledge)│    │  real-time context)        │    │   │
│  │  └────────────────────┘    └────────────────────────────┘    │   │
│  │              │                            │                    │   │
│  │              └────────────┬───────────────┘                   │   │
│  │                           ▼                                    │   │
│  │              ┌─────────────────────────┐                      │   │
│  │              │ Fusion + Generation     │                      │   │
│  │              │ (Historical context +   │                      │   │
│  │              │  Live context → Answer) │                      │   │
│  │              └─────────────────────────┘                      │   │
│  └───────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass, field
from typing import List, Dict, Optional, AsyncIterator
from datetime import datetime, timedelta
from collections import deque
import asyncio

@dataclass
class StreamEvent:
    event_id: str
    source: str         # "iot", "market", "social"
    timestamp: datetime
    data: dict
    embedding: Optional[List[float]] = None

@dataclass
class LiveIndexConfig:
    window_size: timedelta = timedelta(minutes=30)
    max_events: int = 100000
    embedding_batch_size: int = 100
    update_interval_ms: int = 100  # Update index every 100ms

class RealTimeStreamProcessor:
    """Process streaming data for real-time RAG."""
    
    def __init__(self, embedder, live_index, historical_index, pattern_detector):
        self.embedder = embedder
        self.live_index = live_index
        self.historical = historical_index
        self.detector = pattern_detector
        self.event_buffer = deque(maxlen=1000)
    
    async def process_stream(self, event_stream: AsyncIterator[StreamEvent]):
        """Continuous stream processing pipeline."""
        batch = []
        
        async for event in event_stream:
            # 1. Buffer for batch embedding
            batch.append(event)
            
            # 2. Real-time pattern detection (per-event)
            anomaly = await self.detector.check(event)
            if anomaly:
                await self.handle_anomaly(event, anomaly)
            
            # 3. Batch embed and index
            if len(batch) >= 100:
                await self.embed_and_index_batch(batch)
                batch = []
            
            # 4. Window management (evict old events)
            await self.live_index.evict_older_than(
                datetime.utcnow() - timedelta(minutes=30)
            )
    
    async def embed_and_index_batch(self, events: List[StreamEvent]):
        """Embed batch of events and add to live index."""
        # Create text representations for embedding
        texts = [self.event_to_text(e) for e in events]
        
        # Batch embed
        embeddings = await self.embedder.embed_batch(texts)
        
        # Add to live index
        for event, embedding in zip(events, embeddings):
            event.embedding = embedding
            await self.live_index.upsert(
                id=event.event_id,
                vector=embedding,
                metadata={
                    "source": event.source,
                    "timestamp": event.timestamp.isoformat(),
                    "data": event.data
                }
            )
    
    def event_to_text(self, event: StreamEvent) -> str:
        """Convert structured event to text for embedding."""
        if event.source == "iot":
            return f"Sensor {event.data['sensor_id']} reading: {event.data['value']} {event.data['unit']} at {event.timestamp}"
        elif event.source == "market":
            return f"{event.data['symbol']} price: {event.data['price']} volume: {event.data['volume']} at {event.timestamp}"
        elif event.source == "social":
            return f"Post by @{event.data.get('author', 'unknown')}: {event.data['text']}"
        return str(event.data)

class RealTimeRAG:
    """RAG that combines historical knowledge with live streaming context."""
    
    def __init__(self, historical_index, live_index, generator, stream_processor):
        self.historical = historical_index
        self.live = live_index
        self.generator = generator
        self.stream = stream_processor
    
    async def query(self, question: str, 
                    time_context: str = "now",
                    include_live: bool = True) -> dict:
        """Answer questions using both historical and live data."""
        
        query_embedding = await self.embed(question)
        
        # 1. Retrieve from historical knowledge base
        historical_results = await self.historical.query(
            vector=query_embedding,
            top_k=5
        )
        
        # 2. Retrieve from live streaming index
        live_results = []
        if include_live:
            live_results = await self.live.query(
                vector=query_embedding,
                top_k=5,
                filter={"timestamp": {"$gte": (datetime.utcnow() - timedelta(minutes=30)).isoformat()}}
            )
        
        # 3. Get real-time aggregations
        aggregations = await self.stream.get_current_aggregations(question)
        
        # 4. Generate answer with temporal awareness
        context = self.build_temporal_context(historical_results, live_results, aggregations)
        
        response = await self.generator.generate(
            prompt=f"""Answer the question using both historical knowledge and real-time data.
Clearly distinguish between established facts and real-time observations.
Indicate data freshness (e.g., "as of 2 minutes ago").

Historical Context:
{context['historical']}

Real-Time Context (last 30 minutes):
{context['live']}

Current Aggregations:
{context['aggregations']}

Question: {question}
Answer:"""
        )
        
        return {
            "response": response,
            "data_freshness": self.compute_freshness(live_results),
            "sources": {
                "historical": len(historical_results),
                "live": len(live_results)
            }
        }
    
    async def subscribe_to_insights(self, query: str) -> AsyncIterator[dict]:
        """Subscribe to continuous insights (push-based)."""
        last_answer = None
        
        while True:
            # Re-run query periodically or on significant events
            result = await self.query(query, include_live=True)
            
            # Only push if answer meaningfully changed
            if self.has_significant_change(last_answer, result["response"]):
                last_answer = result["response"]
                yield result
            
            await asyncio.sleep(10)  # Check every 10 seconds

class WindowedAggregator:
    """Compute real-time aggregations over streaming windows."""
    
    def __init__(self):
        self.windows = {}  # metric -> sliding window values
    
    async def get_current_aggregations(self, query: str) -> dict:
        """Get relevant real-time stats for a query."""
        return {
            "event_rate": self.compute_event_rate(window="5min"),
            "anomaly_count": self.count_anomalies(window="30min"),
            "trend_direction": self.compute_trend(window="1hour"),
            "top_entities": self.get_top_entities(window="15min", top_k=5),
            "sentiment": self.compute_sentiment(window="30min"),
        }
```

**Dual-Index Strategy:**

| Index | Content | Freshness | Retention | Update Frequency |
|-------|---------|-----------|-----------|-----------------|
| Historical | Documents, past reports, knowledge | Days-years old | Permanent | Batch (daily) |
| Live | Stream events, real-time data | Seconds-minutes | 30-60 min window | Sub-second |
| Aggregation | Computed stats, trends | Current | Sliding window | Continuous |

**Production Considerations:**
- **Embedding latency**: Stream processing requires fast embedding (<10ms); use lightweight model or GPU inference
- **Index update rate**: Live index updates 10-100x per second; use append-only with periodic compaction
- **Temporal decay**: Recent events weighted higher in retrieval; exponential decay function
- **Backpressure**: If stream volume exceeds embedding capacity, sample or aggregate before embedding
- **Consistency**: Live index is eventually consistent; document data freshness in responses
- **Cost**: Embedding every stream event is expensive; sample at high volumes (embed 10% of social media, 100% of IoT alerts)
