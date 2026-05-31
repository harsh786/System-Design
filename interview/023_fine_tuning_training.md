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
