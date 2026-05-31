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
