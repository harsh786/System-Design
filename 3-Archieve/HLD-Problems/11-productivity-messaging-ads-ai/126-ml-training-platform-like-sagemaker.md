# Problem 126: Design ML Training Platform (like SageMaker/Vertex AI)

## Problem Statement

Design a scalable ML Training Platform that enables data scientists and ML engineers to train models efficiently at scale, similar to AWS SageMaker or Google Vertex AI.

## Key Challenges

### Distributed Training
- Data parallelism: replicate model across GPUs, split data batches
- Model parallelism: split large models across multiple GPUs
- Pipeline parallelism: split model layers into stages with micro-batches
- Hybrid parallelism strategies for very large models (100B+ parameters)

### GPU Cluster Management
- Heterogeneous GPU types (A100, H100, T4) with different capabilities
- Topology-aware placement (NVLink, NVSwitch, InfiniBand interconnects)
- GPU health monitoring and automatic node replacement
- Multi-node training across rack boundaries

### Experiment Tracking
- Metrics logging (loss, accuracy, custom metrics) at training step granularity
- Artifact versioning (model weights, datasets, configs)
- Comparison across experiments and reproducibility guarantees

### Hyperparameter Tuning
- Bayesian optimization (Tree-structured Parzen Estimators)
- Early stopping for poorly performing trials
- Parallelized trial execution with resource constraints

### Training Job Scheduling
- Priority-based scheduling with fair-share across teams
- Preemption with checkpoint-and-resume for lower priority jobs
- Gang scheduling (all-or-nothing GPU allocation for distributed jobs)

### Model Checkpointing
- Periodic and on-demand checkpointing to distributed storage
- Incremental checkpoints for large models (100GB+ state)
- Fast checkpoint loading for job resumption

### Data Pipeline Integration
- Streaming data loading from object storage / data lakes
- Data preprocessing and augmentation pipelines
- Caching frequently accessed datasets on local NVMe

### Multi-Tenancy
- Resource isolation between teams/projects
- Quota management (GPU-hours per team)
- Cost attribution and chargeback

## Scale Requirements

- 1,000+ concurrent training jobs
- 10,000+ GPUs in the cluster
- Models up to 1T parameters
- Datasets up to 100TB
- Job durations from minutes to weeks
- 99.9% job completion rate (with retries)

## Expected Output

Provide a complete system design addressing distributed training strategies, cluster scheduling, experiment management, and multi-tenant resource isolation.
