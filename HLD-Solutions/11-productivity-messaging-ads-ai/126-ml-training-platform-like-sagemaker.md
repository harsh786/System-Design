# Solution 126: ML Training Platform (like SageMaker/Vertex AI)

## 1. Requirements Clarification

### Functional Requirements
- Submit training jobs with script, data source, and resource specifications
- Distributed training across multiple GPUs/nodes
- Experiment tracking with metrics, artifacts, and hyperparameters
- Hyperparameter tuning with intelligent search strategies
- Model checkpointing and job resumption
- Job scheduling with priority and preemption

### Non-Functional Requirements
- 1,000+ concurrent training jobs
- 10,000+ GPUs managed
- Job startup latency < 60 seconds
- 99.9% job completion rate (with retries)
- Checkpoint overhead < 5% of training time
- Support models up to 1T parameters

### Out of Scope
- Model serving/inference (separate system)
- Data labeling pipelines
- Feature stores
- IDE integration details

## 2. Back-of-the-Envelope Estimation

### Cluster Size
- 10,000 GPUs (mix of A100 80GB and H100 80GB)
- ~1,250 nodes with 8 GPUs each
- InfiniBand interconnect: 400 Gbps per node
- Total GPU memory: 800 TB

### Storage
- Checkpoint storage: 10,000 jobs × avg 50GB checkpoint = 500 TB active
- Dataset cache: 200 TB on distributed NVMe
- Metrics/logs: ~100 GB/day

### Scheduling
- 1,000 concurrent jobs, avg 8 GPUs each = 8,000 GPUs active
- Job submission rate: ~200 jobs/hour
- Average job duration: 4 hours (high variance: minutes to weeks)

### Network
- AllReduce gradient sync for 1B param model (4GB FP32): every iteration
- At 400 Gbps InfiniBand: ~80ms for 4GB across 8 nodes
- Checkpoint write (50GB) to object storage at 10 Gbps: ~40 seconds

## 3. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ML Training Platform                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────┐  ┌──────────────┐  ┌─────────────┐  ┌────────────┐  │
│  │ Job API  │  │ Experiment   │  │  Tuning     │  │  Dashboard │  │
│  │ Service  │  │ Tracker      │  │  Service    │  │  UI        │  │
│  └────┬─────┘  └──────┬───────┘  └──────┬──────┘  └────────────┘  │
│       │                │                  │                          │
│  ┌────▼────────────────▼──────────────────▼──────────────────────┐  │
│  │                   Control Plane                                │  │
│  │  ┌────────────┐  ┌──────────────┐  ┌─────────────────────┐   │  │
│  │  │ Scheduler  │  │ Resource Mgr │  │ Job State Machine   │   │  │
│  │  └────────────┘  └──────────────┘  └─────────────────────┘   │  │
│  └───────────────────────────┬───────────────────────────────────┘  │
│                              │                                       │
│  ┌───────────────────────────▼───────────────────────────────────┐  │
│  │                    Data Plane (GPU Cluster)                    │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │  │
│  │  │ Node 1  │  │ Node 2  │  │ Node 3  │  │ Node N  │        │  │
│  │  │ 8×H100  │  │ 8×H100  │  │ 8×A100  │  │ 8×A100  │        │  │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘        │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    Storage Layer                              │    │
│  │  ┌──────────┐  ┌─────────────┐  ┌──────────────────────┐   │    │
│  │  │ Object   │  │ Checkpoint  │  │ Dataset Cache (NVMe) │   │    │
│  │  │ Store    │  │ Store       │  │                      │   │    │
│  │  └──────────┘  └─────────────┘  └──────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

## 4. Data Model / Schema Design

### Training Job Definition
```python
@dataclass
class TrainingJob:
    job_id: str                    # UUID
    user_id: str
    team_id: str
    name: str
    status: JobStatus              # PENDING, QUEUED, RUNNING, CHECKPOINTING, COMPLETED, FAILED
    priority: int                  # 0-100, higher = more important
    preemptible: bool
    
    # Script configuration
    entry_point: str               # "train.py"
    source_uri: str                # s3://bucket/code.tar.gz
    framework: Framework           # PYTORCH, TENSORFLOW, JAX
    framework_version: str
    
    # Resource specification
    resource_spec: ResourceSpec
    
    # Data configuration
    data_channels: List[DataChannel]
    
    # Distributed training config
    distribution: DistributionConfig
    
    # Checkpointing
    checkpoint_config: CheckpointConfig
    
    # Scheduling
    max_runtime_seconds: int
    retry_policy: RetryPolicy
    
    # Metadata
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    tags: Dict[str, str]

@dataclass
class ResourceSpec:
    instance_type: str             # "ml.p4d.24xlarge" (8×A100)
    instance_count: int            # Number of nodes
    gpu_count_per_node: int        # GPUs per node
    gpu_memory_gb: int
    cpu_count: int
    memory_gb: int
    local_storage_gb: int          # NVMe scratch space
    
@dataclass
class DistributionConfig:
    strategy: DistStrategy         # DATA_PARALLEL, MODEL_PARALLEL, PIPELINE, HYBRID
    # Data parallel
    backend: str                   # "nccl", "gloo"
    # Pipeline parallel
    pipeline_stages: Optional[int]
    micro_batch_size: Optional[int]
    # Model parallel
    tensor_parallel_degree: Optional[int]
    # ZeRO optimization
    zero_stage: Optional[int]      # 0, 1, 2, or 3

@dataclass
class CheckpointConfig:
    checkpoint_dir: str            # s3://bucket/checkpoints/
    save_interval_steps: int       # Save every N steps
    save_interval_seconds: int     # Or every N seconds
    max_checkpoints_to_keep: int
    resume_from: Optional[str]     # Checkpoint URI to resume from

class JobStatus(Enum):
    PENDING = "pending"
    QUEUED = "queued"
    SCHEDULING = "scheduling"
    INITIALIZING = "initializing"
    DOWNLOADING_DATA = "downloading_data"
    RUNNING = "running"
    CHECKPOINTING = "checkpointing"
    PREEMPTED = "preempted"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

### Experiment Tracking Schema
```python
@dataclass
class Experiment:
    experiment_id: str
    name: str
    project_id: str
    description: str
    created_by: str
    created_at: datetime
    tags: Dict[str, str]

@dataclass
class Run:
    run_id: str                    # Maps to job_id
    experiment_id: str
    hyperparameters: Dict[str, Any]
    metrics: List[MetricEntry]
    artifacts: List[Artifact]
    status: str
    started_at: datetime
    ended_at: Optional[datetime]

@dataclass
class MetricEntry:
    key: str                       # "loss", "accuracy", "learning_rate"
    value: float
    step: int
    timestamp: datetime
    worker_rank: int               # Which GPU/worker reported this

@dataclass
class Artifact:
    artifact_id: str
    name: str
    artifact_type: str             # "model", "dataset", "config"
    uri: str
    size_bytes: int
    metadata: Dict[str, Any]
    created_at: datetime
```

### Cluster State
```python
@dataclass
class GpuNode:
    node_id: str
    hostname: str
    gpu_type: str                  # "A100-80GB", "H100-80GB"
    gpu_count: int
    gpus: List[GpuDevice]
    rack_id: str
    switch_id: str                 # Leaf switch
    infiniband_bandwidth_gbps: int
    status: NodeStatus             # HEALTHY, DEGRADED, MAINTENANCE, OFFLINE
    allocated_jobs: List[str]      # Job IDs using this node
    
@dataclass
class GpuDevice:
    device_id: int
    uuid: str
    memory_total_gb: int
    memory_used_gb: int
    utilization_percent: float
    temperature_celsius: float
    ecc_errors: int
    status: str                    # "available", "allocated", "faulty"
```

## 5. API Design

### Job Management API
```python
# Submit a training job
POST /api/v1/training-jobs
{
    "name": "bert-large-pretraining",
    "entry_point": "train.py",
    "source_uri": "s3://ml-code/bert-train-v2.tar.gz",
    "framework": "pytorch",
    "framework_version": "2.1",
    "resource_spec": {
        "instance_type": "ml.p4d.24xlarge",
        "instance_count": 4,
        "gpu_count_per_node": 8
    },
    "distribution": {
        "strategy": "DATA_PARALLEL",
        "backend": "nccl",
        "zero_stage": 2
    },
    "data_channels": [
        {"name": "training", "uri": "s3://datasets/wiki-corpus/", "mode": "streaming"}
    ],
    "checkpoint_config": {
        "save_interval_steps": 1000,
        "max_checkpoints_to_keep": 3
    },
    "hyperparameters": {
        "learning_rate": "3e-4",
        "batch_size": "32",
        "max_steps": "100000"
    },
    "max_runtime_seconds": 259200,
    "priority": 50,
    "preemptible": true
}

Response: 201 Created
{
    "job_id": "tj-abc123",
    "status": "PENDING",
    "created_at": "2024-01-15T10:00:00Z"
}

# Get job status
GET /api/v1/training-jobs/{job_id}

# Stop a job
POST /api/v1/training-jobs/{job_id}/stop

# List jobs with filtering
GET /api/v1/training-jobs?team_id=ml-team&status=RUNNING&limit=50

# Get job logs (streaming)
GET /api/v1/training-jobs/{job_id}/logs?worker=0&follow=true
```

### Experiment Tracking API
```python
# Log metrics (batch)
POST /api/v1/runs/{run_id}/metrics/batch
{
    "metrics": [
        {"key": "train_loss", "value": 2.34, "step": 1000},
        {"key": "learning_rate", "value": 0.0003, "step": 1000},
        {"key": "gpu_utilization", "value": 0.94, "step": 1000}
    ]
}

# Log artifact
POST /api/v1/runs/{run_id}/artifacts
{
    "name": "model-step-10000",
    "artifact_type": "model",
    "uri": "s3://checkpoints/tj-abc123/step-10000/"
}

# Query metrics (for visualization)
GET /api/v1/runs/{run_id}/metrics?key=train_loss&start_step=0&end_step=10000&sample=100
```

### Hyperparameter Tuning API
```python
# Create tuning job
POST /api/v1/tuning-jobs
{
    "name": "bert-lr-search",
    "base_job_config": { ... },  # Same as training job minus HPs
    "objective": {
        "metric_name": "eval_loss",
        "type": "minimize"
    },
    "search_space": {
        "learning_rate": {"type": "log_uniform", "min": 1e-5, "max": 1e-2},
        "warmup_steps": {"type": "int_uniform", "min": 100, "max": 5000},
        "weight_decay": {"type": "uniform", "min": 0.0, "max": 0.3}
    },
    "strategy": {
        "type": "BAYESIAN",
        "max_trials": 50,
        "max_parallel_trials": 5,
        "early_stopping": {
            "type": "median",
            "min_trials": 5,
            "min_steps": 1000
        }
    },
    "resource_limits": {
        "max_gpu_hours": 500
    }
}
```

## 6. Core Algorithm: Distributed Training

### Ring AllReduce for Data Parallelism
```python
class RingAllReduceGradientSync:
    """
    Ring AllReduce implementation for gradient synchronization.
    Each GPU sends/receives to/from neighbors in a ring topology.
    Completes in 2*(N-1) steps for N GPUs.
    """
    
    def __init__(self, world_size: int, rank: int, backend: str = "nccl"):
        self.world_size = world_size
        self.rank = rank
        self.left_neighbor = (rank - 1) % world_size
        self.right_neighbor = (rank + 1) % world_size
        
    def allreduce(self, tensor: Tensor) -> Tensor:
        """
        Phase 1: Scatter-reduce (N-1 steps)
        - Divide tensor into N chunks
        - Each step: send one chunk right, receive one chunk from left, reduce
        
        Phase 2: All-gather (N-1 steps)
        - Each step: send reduced chunk right, receive from left
        """
        n = self.world_size
        chunks = tensor.chunk(n)
        
        # Phase 1: Scatter-reduce
        for step in range(n - 1):
            send_idx = (self.rank - step) % n
            recv_idx = (self.rank - step - 1) % n
            
            # Async send chunk to right neighbor
            send_op = isend(chunks[send_idx], dst=self.right_neighbor)
            # Receive chunk from left neighbor
            recv_buf = recv(src=self.left_neighbor)
            send_op.wait()
            
            # Reduce received chunk with local chunk
            chunks[recv_idx] = chunks[recv_idx] + recv_buf
            
        # Phase 2: All-gather
        for step in range(n - 1):
            send_idx = (self.rank - step + 1) % n
            recv_idx = (self.rank - step) % n
            
            send_op = isend(chunks[send_idx], dst=self.right_neighbor)
            chunks[recv_idx] = recv(src=self.left_neighbor)
            send_op.wait()
            
        return torch.cat(chunks)


class DataParallelTrainer:
    """
    Data parallel training with gradient synchronization.
    Each worker has a full model copy but processes different data.
    """
    
    def __init__(self, model, optimizer, world_size, rank):
        self.model = model
        self.optimizer = optimizer
        self.world_size = world_size
        self.rank = rank
        self.gradient_sync = RingAllReduceGradientSync(world_size, rank)
        self.scaler = GradScaler()  # For mixed precision
        
    def train_step(self, batch):
        # Forward pass with mixed precision
        with autocast(dtype=torch.float16):
            outputs = self.model(batch['input_ids'], batch['labels'])
            loss = outputs.loss / self.gradient_accumulation_steps
            
        # Backward pass
        self.scaler.scale(loss).backward()
        
        # Synchronize gradients across all workers
        for param in self.model.parameters():
            if param.grad is not None:
                param.grad.data = self.gradient_sync.allreduce(param.grad.data)
                param.grad.data /= self.world_size
        
        # Optimizer step
        self.scaler.step(self.optimizer)
        self.scaler.update()
        self.optimizer.zero_grad()
        
        return loss.item()
```

### Pipeline Parallelism (GPipe-style)
```python
class PipelineParallelTrainer:
    """
    Pipeline parallelism: split model into stages, process micro-batches.
    Reduces bubble time compared to naive model parallelism.
    
    Schedule (4 stages, 4 micro-batches):
    Time →
    Stage 0: |F0|F1|F2|F3|  |  |  |B3|B2|B1|B0|
    Stage 1: |  |F0|F1|F2|F3|  |B3|B2|B1|B0|  |
    Stage 2: |  |  |F0|F1|F2|F3|B3|B2|B1|B0|  |
    Stage 3: |  |  |  |F0|F1|F2|F3|B3|B2|B1|B0|
    """
    
    def __init__(self, model_stages, stage_id, num_micro_batches):
        self.stage = model_stages[stage_id]
        self.stage_id = stage_id
        self.num_stages = len(model_stages)
        self.num_micro_batches = num_micro_batches
        self.activation_buffer = {}  # Store activations for backward
        
    def forward_step(self, micro_batch_id, input_tensor):
        """Process one micro-batch forward through this stage."""
        output = self.stage(input_tensor)
        # Save activation for backward pass
        self.activation_buffer[micro_batch_id] = (input_tensor, output)
        return output
    
    def backward_step(self, micro_batch_id, grad_output):
        """Process one micro-batch backward through this stage."""
        input_tensor, output = self.activation_buffer.pop(micro_batch_id)
        input_tensor.requires_grad_(True)
        
        torch.autograd.backward(output, grad_output)
        return input_tensor.grad
    
    def run_pipeline(self, batches):
        """
        Execute the 1F1B (one forward, one backward) schedule.
        Minimizes memory by overlapping forward and backward.
        """
        micro_batches = [b for b in batches.chunk(self.num_micro_batches)]
        
        # Warm-up: forward passes to fill pipeline
        num_warmup = self.num_stages - self.stage_id - 1
        forward_outputs = []
        
        for i in range(num_warmup):
            if self.stage_id == 0:
                input_t = micro_batches[i]
            else:
                input_t = recv_from_prev_stage()
            
            output = self.forward_step(i, input_t)
            
            if self.stage_id < self.num_stages - 1:
                send_to_next_stage(output)
            forward_outputs.append(output)
        
        # Steady state: 1F1B
        for i in range(num_warmup, self.num_micro_batches):
            # Forward
            if self.stage_id == 0:
                input_t = micro_batches[i]
            else:
                input_t = recv_from_prev_stage()
            output = self.forward_step(i, input_t)
            if self.stage_id < self.num_stages - 1:
                send_to_next_stage(output)
            
            # Backward for earlier micro-batch
            bwd_idx = i - num_warmup
            grad = recv_grad_from_next_stage() if self.stage_id < self.num_stages - 1 else None
            grad_input = self.backward_step(bwd_idx, grad)
            if self.stage_id > 0:
                send_grad_to_prev_stage(grad_input)
        
        # Cool-down: remaining backward passes
        for i in range(num_warmup):
            bwd_idx = self.num_micro_batches - num_warmup + i
            grad = recv_grad_from_next_stage() if self.stage_id < self.num_stages - 1 else None
            grad_input = self.backward_step(bwd_idx, grad)
            if self.stage_id > 0:
                send_grad_to_prev_stage(grad_input)
```

### ZeRO Optimizer (Stage 3)
```python
class ZeROStage3Optimizer:
    """
    ZeRO-3: Partition model parameters, gradients, AND optimizer states.
    Each GPU only holds 1/N of the full model at any time.
    Parameters are gathered on-demand for forward/backward.
    """
    
    def __init__(self, model, optimizer_cls, world_size, rank):
        self.world_size = world_size
        self.rank = rank
        self.param_partitions = {}
        self.optimizer_states = {}
        
        # Partition parameters across GPUs
        for name, param in model.named_parameters():
            partition_size = param.numel() // world_size
            start = rank * partition_size
            end = start + partition_size
            
            # Each GPU keeps only its partition
            self.param_partitions[name] = param.data.view(-1)[start:end].clone()
            
            # Create optimizer state only for local partition
            self.optimizer_states[name] = optimizer_cls([self.param_partitions[name]])
    
    def gather_parameter(self, name, param):
        """All-gather parameter from all partitions before use."""
        gathered = [torch.empty_like(self.param_partitions[name]) for _ in range(self.world_size)]
        dist.all_gather(gathered, self.param_partitions[name])
        param.data = torch.cat(gathered).view(param.shape)
        
    def reduce_scatter_gradient(self, name, param):
        """Reduce-scatter gradient: each GPU gets reduced gradient for its partition."""
        grad_flat = param.grad.data.view(-1)
        partition_size = grad_flat.numel() // self.world_size
        
        # Each GPU receives the sum of gradients for its partition
        output = torch.empty(partition_size, device=grad_flat.device)
        dist.reduce_scatter(output, list(grad_flat.chunk(self.world_size)))
        
        return output / self.world_size
    
    def step(self):
        """Update only local partition of parameters."""
        for name in self.param_partitions:
            self.optimizer_states[name].step()
```

## 7. Deep Dive: GPU Cluster Scheduling

### Gang Scheduler
```python
class GangScheduler:
    """
    Gang scheduling ensures all GPUs for a distributed job are allocated
    simultaneously (all-or-nothing). Prevents deadlocks where jobs hold
    partial resources waiting for more.
    """
    
    def __init__(self, cluster_state: ClusterState):
        self.cluster = cluster_state
        self.queue = PriorityQueue()  # Jobs waiting for resources
        self.running_jobs = {}
        
    def schedule(self) -> List[SchedulingDecision]:
        decisions = []
        
        # Sort queue by priority (with aging to prevent starvation)
        pending_jobs = self.queue.get_sorted_jobs()
        
        for job in pending_jobs:
            allocation = self.try_allocate(job)
            if allocation:
                decisions.append(SchedulingDecision(
                    job_id=job.job_id,
                    action="START",
                    nodes=allocation
                ))
            else:
                # Check if preemption would help
                if job.priority > 80:  # High priority
                    preemption = self.find_preemption_candidates(job)
                    if preemption:
                        decisions.extend(preemption)
                        
        return decisions
    
    def try_allocate(self, job: TrainingJob) -> Optional[List[NodeAllocation]]:
        """
        Topology-aware allocation: prefer nodes on same switch/rack
        for better InfiniBand performance.
        """
        required_nodes = job.resource_spec.instance_count
        required_gpus_per_node = job.resource_spec.gpu_count_per_node
        gpu_type = job.resource_spec.gpu_type
        
        # Find available nodes matching requirements
        candidates = self.cluster.get_available_nodes(
            gpu_type=gpu_type,
            min_free_gpus=required_gpus_per_node
        )
        
        if len(candidates) < required_nodes:
            return None
            
        # Topology-aware selection: minimize communication hops
        selected = self.select_topology_aware(candidates, required_nodes)
        
        if not selected:
            return None
            
        return [NodeAllocation(node_id=n.node_id, gpus=required_gpus_per_node) 
                for n in selected]
    
    def select_topology_aware(self, candidates, count):
        """
        Prefer nodes connected via:
        1. Same NVSwitch (intra-node) - fastest
        2. Same leaf switch (same rack) - fast InfiniBand
        3. Same spine switch (same pod) - good InfiniBand
        4. Cross-pod - acceptable but slower
        """
        # Group by rack
        racks = defaultdict(list)
        for node in candidates:
            racks[node.rack_id].append(node)
        
        # Try to fit in single rack first
        for rack_id, nodes in sorted(racks.items(), key=lambda x: -len(x[1])):
            if len(nodes) >= count:
                return nodes[:count]
        
        # Try adjacent racks (same pod/spine switch)
        pods = defaultdict(list)
        for node in candidates:
            pods[node.pod_id].append(node)
            
        for pod_id, nodes in sorted(pods.items(), key=lambda x: -len(x[1])):
            if len(nodes) >= count:
                return nodes[:count]
        
        # Fall back to any available nodes
        return candidates[:count] if len(candidates) >= count else None
    
    def find_preemption_candidates(self, high_priority_job):
        """
        Find running lower-priority preemptible jobs to evict.
        Minimize number of preemptions needed.
        """
        preemptible_jobs = [
            j for j in self.running_jobs.values()
            if j.preemptible and j.priority < high_priority_job.priority
        ]
        
        # Sort by priority (lowest first) then by runtime (shortest first)
        preemptible_jobs.sort(key=lambda j: (j.priority, j.runtime))
        
        freed_gpus = 0
        needed_gpus = (high_priority_job.resource_spec.instance_count * 
                      high_priority_job.resource_spec.gpu_count_per_node)
        victims = []
        
        for job in preemptible_jobs:
            victims.append(job)
            freed_gpus += job.allocated_gpus
            if freed_gpus >= needed_gpus:
                break
                
        if freed_gpus >= needed_gpus:
            return [SchedulingDecision(job_id=v.job_id, action="PREEMPT") for v in victims]
        return None


class FairShareScheduler:
    """
    Fair-share scheduling across teams with quotas.
    Teams that have used less than their fair share get priority.
    """
    
    def __init__(self, team_quotas: Dict[str, TeamQuota]):
        self.quotas = team_quotas
        
    def compute_priority_boost(self, job: TrainingJob) -> float:
        team = self.quotas[job.team_id]
        
        # Fair share ratio: actual usage / entitled share
        fair_share_ratio = team.current_gpu_hours / team.quota_gpu_hours
        
        # Teams below their fair share get a boost
        if fair_share_ratio < 1.0:
            boost = (1.0 - fair_share_ratio) * 50  # Up to +50 priority
        else:
            boost = -((fair_share_ratio - 1.0) * 20)  # Penalty for over-use
            
        return job.priority + boost
```

### Bin-Packing with Fragmentation Avoidance
```python
class GpuBinPacker:
    """
    Pack jobs onto GPU nodes minimizing fragmentation.
    Fragmentation occurs when free GPUs are spread across many nodes,
    preventing large jobs from scheduling.
    """
    
    def score_allocation(self, node: GpuNode, job: TrainingJob) -> float:
        """
        Score a node for a job. Higher = better fit.
        Balances utilization vs fragmentation avoidance.
        """
        gpus_needed = job.resource_spec.gpu_count_per_node
        gpus_free = node.free_gpu_count
        gpus_total = node.gpu_count
        
        if gpus_free < gpus_needed:
            return -1  # Cannot fit
        
        # Prefer nodes where job fills remaining capacity (reduces fragmentation)
        remaining_after = gpus_free - gpus_needed
        
        # Best: job exactly fills node (0 remaining)
        # Good: leaves enough for common job sizes (2, 4, 8)
        # Bad: leaves 1, 3, 5, 7 GPUs (hard to fill)
        
        if remaining_after == 0:
            return 100  # Perfect fit
        elif remaining_after in [2, 4, 8]:
            return 80   # Good remainder
        elif remaining_after in [1, 3, 5, 7]:
            return 40   # Awkward remainder
        else:
            return 60
```

## 8. Deep Dive: Checkpointing and Fault Tolerance

### Async Checkpointing
```python
class AsyncCheckpointer:
    """
    Checkpoint training state without blocking training.
    Uses CPU memory as staging area, writes to storage in background.
    """
    
    def __init__(self, storage_client, max_concurrent_writes=2):
        self.storage = storage_client
        self.write_pool = ThreadPoolExecutor(max_workers=max_concurrent_writes)
        self.pending_checkpoints = []
        
    def save_checkpoint(self, model, optimizer, step, metrics):
        """
        Non-blocking checkpoint save:
        1. Copy GPU tensors to CPU (fast, overlaps with next forward pass)
        2. Serialize and write to storage in background thread
        """
        # Phase 1: GPU → CPU copy (synchronized)
        checkpoint_data = {
            'step': step,
            'model_state_dict': {k: v.cpu().clone() for k, v in model.state_dict().items()},
            'optimizer_state_dict': self._copy_optimizer_state(optimizer),
            'metrics': metrics,
            'rng_states': {
                'python': random.getstate(),
                'numpy': np.random.get_state(),
                'torch': torch.random.get_rng_state(),
                'cuda': torch.cuda.get_rng_state_all(),
            }
        }
        
        # Phase 2: Background write to storage
        future = self.write_pool.submit(self._write_checkpoint, checkpoint_data, step)
        self.pending_checkpoints.append(future)
        
        # Cleanup old futures
        self.pending_checkpoints = [f for f in self.pending_checkpoints if not f.done()]
        
    def _write_checkpoint(self, data, step):
        """Write checkpoint to distributed storage (runs in background)."""
        path = f"checkpoints/step-{step}/"
        
        # Write sharded: each large tensor as separate file for parallel I/O
        manifest = {'step': step, 'shards': []}
        
        for key, tensor in data['model_state_dict'].items():
            shard_path = f"{path}model/{key}.pt"
            self.storage.write(shard_path, tensor_to_bytes(tensor))
            manifest['shards'].append({'key': key, 'path': shard_path, 'shape': list(tensor.shape)})
        
        # Write optimizer state
        self.storage.write(f"{path}optimizer.pt", serialize(data['optimizer_state_dict']))
        
        # Write manifest last (atomic marker that checkpoint is complete)
        self.storage.write(f"{path}manifest.json", json.dumps(manifest))
        
    def load_checkpoint(self, step, model, optimizer):
        """Load checkpoint with parallel shard reading."""
        path = f"checkpoints/step-{step}/"
        manifest = json.loads(self.storage.read(f"{path}manifest.json"))
        
        # Parallel shard loading
        with ThreadPoolExecutor(max_workers=16) as pool:
            futures = {}
            for shard in manifest['shards']:
                futures[shard['key']] = pool.submit(self.storage.read, shard['path'])
            
            state_dict = {}
            for key, future in futures.items():
                state_dict[key] = bytes_to_tensor(future.result())
        
        model.load_state_dict(state_dict)


class ElasticTraining:
    """
    Elastic training: handle node failures gracefully without killing the job.
    Inspired by PyTorch Elastic (torchelastic).
    """
    
    def __init__(self, min_nodes, max_nodes, checkpoint_manager):
        self.min_nodes = min_nodes
        self.max_nodes = max_nodes
        self.checkpoint_mgr = checkpoint_manager
        self.current_world_size = max_nodes
        
    def handle_node_failure(self, failed_node_id):
        """
        On node failure:
        1. Detect failure (heartbeat timeout)
        2. If remaining nodes >= min_nodes: reconfigure and continue
        3. If remaining nodes < min_nodes: checkpoint and wait for replacement
        """
        remaining = self.current_world_size - 1
        
        if remaining >= self.min_nodes:
            # Reconfigure: adjust world size, re-partition data
            self.current_world_size = remaining
            self.reconfigure_distributed_group()
            self.redistribute_data_shards()
            # Continue training with fewer nodes (larger per-GPU batch)
        else:
            # Must wait: checkpoint current state
            self.checkpoint_mgr.save_checkpoint_sync()
            self.wait_for_replacement_node()
            self.current_world_size = self.min_nodes
            self.reconfigure_distributed_group()
            self.resume_from_checkpoint()
```

## 9. Hyperparameter Tuning

### Bayesian Optimization with TPE
```python
class BayesianHyperparameterTuner:
    """
    Tree-structured Parzen Estimator (TPE) for hyperparameter optimization.
    Models P(x|y<y*) and P(x|y>=y*) separately, maximizes their ratio.
    """
    
    def __init__(self, search_space: Dict[str, SearchDimension], objective: str):
        self.search_space = search_space
        self.objective = objective
        self.trials: List[Trial] = []
        self.gamma = 0.25  # Top 25% threshold
        
    def suggest_next_trial(self) -> Dict[str, Any]:
        if len(self.trials) < 10:
            # Random search for initial exploration
            return self._random_sample()
        
        # Split trials into good (l) and bad (g) based on objective
        sorted_trials = sorted(self.trials, key=lambda t: t.objective_value)
        n_good = max(1, int(self.gamma * len(sorted_trials)))
        
        good_trials = sorted_trials[:n_good]
        bad_trials = sorted_trials[n_good:]
        
        # For each hyperparameter, fit KDE to good and bad distributions
        suggestion = {}
        for param_name, dim in self.search_space.items():
            good_values = [t.params[param_name] for t in good_trials]
            bad_values = [t.params[param_name] for t in bad_trials]
            
            # Sample candidates and pick one that maximizes l(x)/g(x)
            candidates = self._sample_candidates(dim, n=24)
            
            l_scores = self._kde_score(good_values, candidates, dim)
            g_scores = self._kde_score(bad_values, candidates, dim)
            
            # Expected improvement proxy: maximize l(x)/g(x)
            ei_scores = l_scores / (g_scores + 1e-10)
            best_idx = np.argmax(ei_scores)
            suggestion[param_name] = candidates[best_idx]
            
        return suggestion
    
    def _kde_score(self, observations, candidates, dim):
        """Kernel density estimation score for candidates."""
        if dim.type == 'log_uniform':
            observations = np.log(observations)
            candidates = np.log(candidates)
            
        bandwidth = self._adaptive_bandwidth(observations)
        scores = np.zeros(len(candidates))
        
        for obs in observations:
            scores += np.exp(-0.5 * ((candidates - obs) / bandwidth) ** 2)
            
        return scores / len(observations)


class EarlyStoppingMedian:
    """
    Median early stopping: stop trials performing below median at same step.
    """
    
    def __init__(self, min_trials: int = 5, min_steps: int = 1000):
        self.min_trials = min_trials
        self.min_steps = min_steps
        
    def should_stop(self, trial: Trial, all_trials: List[Trial]) -> bool:
        completed_trials = [t for t in all_trials if t.status == 'COMPLETED']
        
        if len(completed_trials) < self.min_trials:
            return False
            
        if trial.current_step < self.min_steps:
            return False
            
        # Get metric values at current step for completed trials
        step = trial.current_step
        other_values = []
        for t in completed_trials:
            value_at_step = t.get_metric_at_step(step)
            if value_at_step is not None:
                other_values.append(value_at_step)
        
        if not other_values:
            return False
            
        median_value = np.median(other_values)
        current_value = trial.get_current_metric()
        
        # Stop if worse than median (assuming minimization)
        return current_value > median_value * 1.1  # 10% grace margin
```

## 10. Production Configuration

### Kubernetes-based Deployment
```yaml
# Training Operator CRD for PyTorch distributed jobs
apiVersion: kubeflow.org/v1
kind: PyTorchJob
metadata:
  name: bert-large-pretraining
  namespace: ml-training
spec:
  elasticPolicy:
    minReplicas: 2
    maxReplicas: 4
    rdzvBackend: etcd
    rdzvEndpoint: "etcd-service:2379"
  pytorchReplicaSpecs:
    Master:
      replicas: 1
      template:
        spec:
          containers:
          - name: pytorch
            image: ml-platform/pytorch-training:2.1-cuda12.1
            command: ["torchrun"]
            args:
              - "--nnodes=4"
              - "--nproc_per_node=8"
              - "--rdzv_backend=etcd"
              - "train.py"
            resources:
              limits:
                nvidia.com/gpu: 8
                rdma/rdma_shared_device_a: 1
              requests:
                memory: "512Gi"
                cpu: "96"
            volumeMounts:
            - name: dshm
              mountPath: /dev/shm
            - name: nvme-scratch
              mountPath: /scratch
          volumes:
          - name: dshm
            emptyDir:
              medium: Memory
              sizeLimit: "256Gi"
          - name: nvme-scratch
            hostPath:
              path: /mnt/nvme
          nodeSelector:
            gpu-type: "h100"
            network: "infiniband-400g"
          tolerations:
          - key: "nvidia.com/gpu"
            operator: "Exists"
            effect: "NoSchedule"
    Worker:
      replicas: 3
      template:
        spec:
          containers:
          - name: pytorch
            # Same as master
            ...

---
# Cluster autoscaler configuration
apiVersion: v1
kind: ConfigMap
metadata:
  name: gpu-scheduler-config
data:
  policy.yaml: |
    scheduling:
      gang_scheduling:
        enabled: true
        timeout_seconds: 300
      topology_aware:
        enabled: true
        prefer_same_rack: true
        prefer_same_switch: true
      preemption:
        enabled: true
        grace_period_seconds: 60
        checkpoint_before_preempt: true
      fair_share:
        enabled: true
        decay_factor: 0.95
        interval_hours: 24
      quotas:
        ml-research:
          gpu_hours_per_day: 5000
          max_concurrent_gpus: 512
          max_job_duration_hours: 168
        ml-production:
          gpu_hours_per_day: 10000
          max_concurrent_gpus: 2048
          max_job_duration_hours: 720
          priority_boost: 20
```

### Monitoring Configuration
```yaml
# Prometheus metrics for GPU cluster
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: gpu-cluster-alerts
spec:
  groups:
  - name: gpu-health
    rules:
    - alert: GpuHighTemperature
      expr: gpu_temperature_celsius > 85
      for: 5m
      labels:
        severity: warning
    - alert: GpuEccErrors
      expr: increase(gpu_ecc_errors_total[1h]) > 10
      for: 0m
      labels:
        severity: critical
    - alert: GpuUtilizationLow
      expr: avg(gpu_utilization_percent{job_status="running"}) < 50
      for: 30m
      labels:
        severity: warning
        description: "Training job may be I/O bound"
    - alert: TrainingJobStuck
      expr: increase(training_step_total[30m]) == 0 and job_status == "running"
      for: 0m
      labels:
        severity: critical
    - alert: CheckpointWriteSlow
      expr: histogram_quantile(0.99, checkpoint_write_duration_seconds) > 120
      for: 5m
      labels:
        severity: warning
  - name: scheduler
    rules:
    - alert: JobQueueBacklog
      expr: scheduler_pending_jobs > 100
      for: 15m
    - alert: GpuFragmentation
      expr: scheduler_fragmented_gpus / scheduler_total_gpus > 0.2
      for: 30m
```

## 11. Failure Scenarios and Mitigations

| Failure | Impact | Mitigation |
|---------|--------|------------|
| Single GPU failure | One worker in distributed job fails | Elastic training: reconfigure with remaining nodes; if below min, checkpoint and wait |
| Network partition between nodes | Gradient sync hangs (NCCL timeout) | NCCL timeout detection → checkpoint → reschedule on healthy nodes |
| Checkpoint storage unavailable | Cannot save progress | Write to local NVMe as fallback, retry to remote; alert if >2 missed checkpoints |
| OOM during training | Job crashes | Auto-retry with gradient accumulation (effective same batch size, less memory) |
| Data pipeline stall | GPUs idle waiting for data | Prefetch buffer (3-5 batches), alert on pipeline throughput drop |
| Scheduler crash | No new jobs scheduled | Scheduler HA with leader election; running jobs unaffected |
| Preemption storm | Many jobs checkpointing simultaneously | Rate-limit preemptions (max 5% of cluster per minute), stagger checkpoint writes |
| NaN in gradients | Training diverges | Gradient norm monitoring, auto-rollback to last good checkpoint |
| InfiniBand link failure | Reduced bandwidth between nodes | NCCL automatic failover to alternate paths; reschedule if critical |
| Quota exhaustion | Team cannot launch new jobs | Graceful notification, queue with lower priority, admin override option |

### Observability Stack
```
┌─────────────────────────────────────────────────────┐
│                  Observability                        │
├──────────────┬──────────────┬───────────────────────┤
│  Metrics     │  Logs        │  Traces               │
│  - GPU util  │  - Job logs  │  - Job lifecycle      │
│  - Loss      │  - Scheduler │  - Scheduling latency │
│  - Throughput│  - Errors    │  - Data loading time  │
│  - Queue     │  - Checkpoint│  - Gradient sync time │
│  (Prometheus)│  (Loki)      │  (Jaeger)             │
└──────────────┴──────────────┴───────────────────────┘
```

### Key Observability Metrics
- **Training efficiency**: GPU utilization, samples/second, time breakdown (compute vs communication vs I/O)
- **Cluster efficiency**: GPU allocation rate, fragmentation %, queue wait time
- **Job health**: loss curve progression, gradient norms, learning rate schedule
- **System health**: node availability, network bandwidth utilization, storage IOPS
