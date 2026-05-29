# CI/CD Platform

## 1. Requirements

### Functional Requirements
- **Pipeline Definition**: YAML DSL for defining build/test/deploy workflows
- **Trigger Management**: Push, PR, schedule (cron), manual, tag, webhook triggers
- **Distributed Build Execution**: Parallel job execution across worker pool
- **Artifact Management**: Build outputs storage with versioning and promotion
- **Environment Management**: Dev/staging/prod with approval gates
- **Deployment Strategies**: Rolling, blue-green, canary with auto-rollback
- **Secret Injection**: Secure secret management for build and deploy steps
- **Build Cache**: Shared cache across runs (Docker layers, dependencies, build outputs)
- **Parallel Job Execution**: Matrix builds, fan-out/fan-in patterns
- **Reusable Workflows**: Shared pipeline templates across repos

### Non-Functional Requirements
- **Availability**: 99.95% for pipeline execution (builds are not hard real-time)
- **Latency**: Job pickup <5s from trigger, build cache hit <500ms
- **Scale**: 100K pipeline runs/day, 10K concurrent jobs, 50K repos
- **Isolation**: Complete workspace isolation between jobs (no cross-contamination)
- **Durability**: Build logs and artifacts retained per policy
- **Security**: No secret leakage, hermetic builds, supply chain integrity

## 2. Capacity Estimation

### Traffic
- Pipeline triggers: 100K/day (~5K/hour peak during work hours)
- Concurrent jobs: 10K peak (average job duration: 5 minutes)
- Artifact uploads: 50K/day × 100MB avg = 5TB/day
- Build cache reads: 200K/day, writes: 50K/day
- Log ingestion: 10K concurrent × 100 lines/s = 1M log lines/second

### Storage
- Artifacts: 5TB/day × 30 days retention = 150TB
- Build cache: 50TB (content-addressable, deduplicated)
- Build logs: 1M lines/s × 200 bytes × 86400s = 17TB/day (compressed to ~2TB)
- Pipeline definitions: 50K repos × 10KB = 500MB (negligible)

### Compute
- Workers: 10K concurrent jobs × 2 vCPU avg = 20K vCPUs
- Controller: 100K orchestrations/day, lightweight
- Cache service: 250K ops/day, high IOPS

## 3. Data Modeling

### Database Schemas

```sql
-- Pipeline Definitions (versioned, from YAML)
CREATE TABLE pipelines (
    pipeline_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repo_id             UUID NOT NULL,
    repo_url            VARCHAR(500) NOT NULL,
    branch              VARCHAR(255) NOT NULL DEFAULT 'main',
    config_path         VARCHAR(500) NOT NULL DEFAULT '.ci/pipeline.yaml',
    name                VARCHAR(255) NOT NULL,
    description         TEXT,
    triggers            JSONB NOT NULL DEFAULT '[]',
    default_branch      VARCHAR(255) DEFAULT 'main',
    settings            JSONB DEFAULT '{}',
    secrets_policy      JSONB DEFAULT '{}',
    is_active           BOOLEAN DEFAULT true,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_pipelines_repo ON pipelines(repo_id, is_active);
CREATE INDEX idx_pipelines_name ON pipelines(name);

-- Pipeline Runs (executions)
CREATE TABLE pipeline_runs (
    run_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_id         UUID NOT NULL REFERENCES pipelines(pipeline_id),
    run_number          BIGINT NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'QUEUED',
    trigger_type        VARCHAR(20) NOT NULL,      -- PUSH, PR, SCHEDULE, MANUAL, TAG
    trigger_event       JSONB NOT NULL,            -- Full trigger context
    git_ref             VARCHAR(255) NOT NULL,
    git_sha             VARCHAR(40) NOT NULL,
    git_message         TEXT,
    author              VARCHAR(255),
    branch              VARCHAR(255),
    pr_number           INT,
    pipeline_config     JSONB NOT NULL,            -- Resolved YAML at run time
    environment         VARCHAR(50),
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    duration_ms         BIGINT,
    conclusion          VARCHAR(20),               -- SUCCESS, FAILURE, CANCELLED, TIMED_OUT
    error_message       TEXT,
    retry_of            UUID,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    CHECK (status IN ('QUEUED','PENDING','RUNNING','COMPLETED','CANCELLED')),
    CHECK (conclusion IN ('SUCCESS','FAILURE','CANCELLED','TIMED_OUT','SKIPPED')),
    UNIQUE(pipeline_id, run_number)
);

CREATE INDEX idx_runs_pipeline ON pipeline_runs(pipeline_id, created_at DESC);
CREATE INDEX idx_runs_status ON pipeline_runs(status, created_at);
CREATE INDEX idx_runs_sha ON pipeline_runs(git_sha);
CREATE INDEX idx_runs_branch ON pipeline_runs(pipeline_id, branch, created_at DESC);
CREATE INDEX idx_runs_trigger ON pipeline_runs(trigger_type, created_at DESC);

-- Jobs (individual units of work within a run)
CREATE TABLE jobs (
    job_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id              UUID NOT NULL REFERENCES pipeline_runs(run_id),
    name                VARCHAR(255) NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    runner_id           VARCHAR(100),              -- Assigned worker
    container_image     VARCHAR(500),
    steps               JSONB NOT NULL,            -- Step definitions
    matrix_values       JSONB,                     -- Matrix combination for this job
    depends_on          UUID[],                    -- Job dependencies (DAG edges)
    environment         VARCHAR(50),
    outputs             JSONB DEFAULT '{}',        -- Output variables for downstream jobs
    timeout_minutes     INT DEFAULT 60,
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    duration_ms         BIGINT,
    conclusion          VARCHAR(20),
    exit_code           INT,
    log_url             VARCHAR(500),
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    CHECK (status IN ('PENDING','QUEUED','RUNNING','COMPLETED','CANCELLED','SKIPPED'))
);

CREATE INDEX idx_jobs_run ON jobs(run_id);
CREATE INDEX idx_jobs_status ON jobs(status, created_at);
CREATE INDEX idx_jobs_runner ON jobs(runner_id, status);

-- Job Steps
CREATE TABLE job_steps (
    step_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id              UUID NOT NULL REFERENCES jobs(job_id),
    name                VARCHAR(255) NOT NULL,
    step_type           VARCHAR(20) NOT NULL,      -- RUN, ACTION, CACHE, ARTIFACT
    command             TEXT,
    action_ref          VARCHAR(255),              -- action@version
    inputs              JSONB DEFAULT '{}',
    outputs             JSONB DEFAULT '{}',
    status              VARCHAR(20) DEFAULT 'PENDING',
    exit_code           INT,
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    duration_ms         BIGINT,
    log_offset          BIGINT,                    -- Start offset in job log
    log_length          BIGINT,
    step_order          INT NOT NULL
);

CREATE INDEX idx_steps_job ON job_steps(job_id, step_order);

-- Artifacts
CREATE TABLE artifacts (
    artifact_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id              UUID NOT NULL REFERENCES pipeline_runs(run_id),
    job_id              UUID REFERENCES jobs(job_id),
    name                VARCHAR(255) NOT NULL,
    path                VARCHAR(500) NOT NULL,     -- Storage path
    size_bytes          BIGINT NOT NULL,
    content_hash        VARCHAR(64) NOT NULL,      -- SHA-256
    content_type        VARCHAR(100),
    retention_days      INT DEFAULT 30,
    metadata            JSONB DEFAULT '{}',
    expires_at          TIMESTAMPTZ NOT NULL,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_artifacts_run ON artifacts(run_id);
CREATE INDEX idx_artifacts_name ON artifacts(name, created_at DESC);
CREATE INDEX idx_artifacts_expiry ON artifacts(expires_at);

-- Build Cache
CREATE TABLE build_cache (
    cache_key           VARCHAR(255) PRIMARY KEY,  -- content-addressable key
    content_hash        VARCHAR(64) NOT NULL,
    storage_path        VARCHAR(500) NOT NULL,
    size_bytes          BIGINT NOT NULL,
    scope               VARCHAR(255) NOT NULL,     -- repo/branch scope
    last_accessed_at    TIMESTAMPTZ DEFAULT NOW(),
    access_count        INT DEFAULT 1,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cache_scope ON build_cache(scope, last_accessed_at DESC);
CREATE INDEX idx_cache_access ON build_cache(last_accessed_at);

-- Environments
CREATE TABLE environments (
    environment_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_id         UUID NOT NULL REFERENCES pipelines(pipeline_id),
    name                VARCHAR(100) NOT NULL,
    tier                VARCHAR(20) NOT NULL,       -- DEV, STAGING, PRODUCTION
    deployment_targets  JSONB NOT NULL,             -- K8s clusters, cloud accounts
    protection_rules    JSONB DEFAULT '{}',         -- Required reviewers, wait timer
    secrets             JSONB DEFAULT '[]',         -- Secret references (not values)
    variables           JSONB DEFAULT '{}',         -- Environment variables
    current_deployment  UUID,                       -- Currently active deployment
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(pipeline_id, name)
);

CREATE INDEX idx_environments_pipeline ON environments(pipeline_id);

-- Deployments
CREATE TABLE deployments (
    deployment_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    environment_id      UUID NOT NULL REFERENCES environments(environment_id),
    run_id              UUID NOT NULL REFERENCES pipeline_runs(run_id),
    strategy            VARCHAR(20) NOT NULL,       -- ROLLING, BLUE_GREEN, CANARY
    status              VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    artifact_id         UUID REFERENCES artifacts(artifact_id),
    config              JSONB NOT NULL,             -- Strategy-specific config
    progress            JSONB DEFAULT '{}',         -- Rollout progress
    health_checks       JSONB DEFAULT '[]',
    approved_by         UUID[],
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    rolled_back_at      TIMESTAMPTZ,
    rollback_reason     TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    CHECK (status IN ('PENDING','APPROVED','IN_PROGRESS','COMPLETED','FAILED','ROLLED_BACK')),
    CHECK (strategy IN ('ROLLING','BLUE_GREEN','CANARY','RECREATE'))
);

CREATE INDEX idx_deployments_env ON deployments(environment_id, created_at DESC);
CREATE INDEX idx_deployments_status ON deployments(status);

-- Secrets (references, actual values in Vault)
CREATE TABLE pipeline_secrets (
    secret_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_type          VARCHAR(20) NOT NULL,       -- ORG, REPO, ENVIRONMENT
    scope_id            UUID NOT NULL,
    name                VARCHAR(255) NOT NULL,
    vault_path          VARCHAR(500) NOT NULL,      -- Reference to actual secret
    last_rotated_at     TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(scope_type, scope_id, name)
);

CREATE INDEX idx_secrets_scope ON pipeline_secrets(scope_type, scope_id);
```

### Kafka Topics

```yaml
topics:
  pipeline-triggers:
    partitions: 32
    replication-factor: 3
    retention.ms: 86400000

  job-assignments:
    partitions: 128              # High throughput for job scheduling
    replication-factor: 3
    retention.ms: 3600000

  job-status-updates:
    partitions: 64
    replication-factor: 3
    retention.ms: 604800000
    cleanup.policy: compact

  build-logs:
    partitions: 256              # Very high throughput
    replication-factor: 2        # Logs less critical
    retention.ms: 86400000
    max.message.bytes: 1048576

  deployment-events:
    partitions: 32
    replication-factor: 3
    retention.ms: 2592000000    # 30 days
```

### Redis Configuration

```yaml
redis:
  job-queue:
    cluster: true
    nodes: 6
    maxmemory: 16gb
    maxmemory-policy: noeviction
    data-structures:
      - sorted-set: "queue:jobs:pending"          # Priority queue
      - hash: "job:state:{job_id}"                # Job state machine
      - set: "runners:available:{pool}"           # Available runners per pool
      - hash: "runner:state:{runner_id}"          # Runner info
      - string: "lock:run:{run_id}"               # Distributed lock

  build-cache-index:
    cluster: true
    nodes: 3
    maxmemory: 8gb
    maxmemory-policy: allkeys-lfu
    data-structures:
      - hash: "cache:index:{scope}"               # Cache key → storage path
      - sorted-set: "cache:lru:{scope}"           # LRU tracking
```

## 4. High-Level Design

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                              CI/CD PLATFORM                                            │
├──────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  Trigger Sources:                                                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐           │
│  │Git Push  │ │PR Event  │ │Cron      │ │Manual    │ │External Webhook  │           │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────────┬─────────┘           │
│       └─────────────┴────────────┴─────────────┴────────────────┘                     │
│                                    │                                                   │
│                                    ▼                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│  │                         Control Plane                                            │  │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                    │  │
│  │  │ Trigger Handler│  │ Pipeline Engine │  │ Scheduler      │                    │  │
│  │  │ (webhook recv, │──▶│ (DAG resolver, │──▶│ (job dispatch, │                    │  │
│  │  │  event filter) │  │  YAML parse)   │  │  resource mgmt)│                    │  │
│  │  └────────────────┘  └────────────────┘  └───────┬────────┘                    │  │
│  └───────────────────────────────────────────────────┼─────────────────────────────┘  │
│                                                       │                                │
│                                                       ▼                                │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│  │                       Worker Pool (Auto-scaling)                                  │  │
│  │                                                                                   │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │  │
│  │  │  Worker 1   │  │  Worker 2   │  │  Worker 3   │  │  Worker N   │           │  │
│  │  │  ┌───────┐  │  │  ┌───────┐  │  │  ┌───────┐  │  │  ┌───────┐  │           │  │
│  │  │  │Container│ │  │  │Container│ │  │  │Container│ │  │  │Container│ │           │  │
│  │  │  │(Job A) │  │  │  │(Job B) │  │  │  │(Job C) │  │  │  │(Job D) │  │           │  │
│  │  │  └───────┘  │  │  └───────┘  │  │  └───────┘  │  │  └───────┘  │           │  │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘           │  │
│  │         └─────────────────┴─────────────────┴────────────────┘                   │  │
│  └───────────────────────────────────────────────┬─────────────────────────────────┘  │
│                                                   │                                    │
│  ┌────────────────────────────────────────────────┼────────────────────────────────┐  │
│  │                       Storage Layer             │                                │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌────────▼─────┐  ┌───────────────────┐  │  │
│  │  │  Artifact    │  │  Build Cache │  │  Log Store   │  │  Secret Store     │  │  │
│  │  │  Store (S3)  │  │  (CAS, S3)  │  │  (S3+ES)    │  │  (Vault)          │  │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └───────────────────┘  │  │
│  └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                        │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│  │                     Deployment Layer                                              │  │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────────┐  │  │
│  │  │ Deploy Controller│  │ Health Monitor   │  │ Rollback Engine              │  │  │
│  │  │ (strategy exec)  │  │ (metric analysis)│  │ (auto + manual)             │  │  │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────────────────┘  │  │
│  └─────────────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

## 5. Low-Level Design (APIs)

### Pipeline APIs

```yaml
# Trigger Pipeline Run
POST /api/v1/pipelines/{pipeline_id}/runs
Request:
  {
    "ref": "refs/heads/feature/new-payment",
    "sha": "abc123def456",
    "trigger_type": "MANUAL",
    "inputs": {
      "deploy_environment": "staging",
      "skip_tests": false
    }
  }
Response: 201
  {
    "run_id": "run_a1b2c3",
    "run_number": 142,
    "status": "QUEUED",
    "jobs": [
      { "job_id": "job_x1", "name": "lint", "status": "PENDING" },
      { "job_id": "job_x2", "name": "test", "status": "PENDING", "depends_on": ["job_x1"] },
      { "job_id": "job_x3", "name": "build", "status": "PENDING", "depends_on": ["job_x2"] },
      { "job_id": "job_x4", "name": "deploy-staging", "status": "PENDING", "depends_on": ["job_x3"] }
    ],
    "created_at": "2024-01-15T10:00:00Z"
  }

# Get Run Status
GET /api/v1/runs/{run_id}
Response: 200
  {
    "run_id": "run_a1b2c3",
    "run_number": 142,
    "status": "RUNNING",
    "conclusion": null,
    "jobs": [
      { "job_id": "job_x1", "name": "lint", "status": "COMPLETED", "conclusion": "SUCCESS", "duration_ms": 45000 },
      { "job_id": "job_x2", "name": "test", "status": "RUNNING", "progress": {"completed_steps": 3, "total_steps": 5} },
      { "job_id": "job_x3", "name": "build", "status": "PENDING" },
      { "job_id": "job_x4", "name": "deploy-staging", "status": "PENDING" }
    ],
    "started_at": "2024-01-15T10:00:02Z",
    "elapsed_ms": 120000
  }

# Stream Job Logs
GET /api/v1/jobs/{job_id}/logs?follow=true&since=0
Response: 200 (streaming, text/plain)
  [2024-01-15T10:00:05Z] Step 1/5: Setup environment
  [2024-01-15T10:00:05Z] Pulling container image: node:20-alpine
  [2024-01-15T10:00:08Z] Image pulled in 3.2s
  [2024-01-15T10:00:08Z] Step 2/5: Restore cache
  [2024-01-15T10:00:09Z] Cache hit: node_modules (key: deps-sha256-abc123)
  ...

# Create Deployment
POST /api/v1/environments/{env_id}/deployments
Request:
  {
    "run_id": "run_a1b2c3",
    "artifact_id": "art_d4e5f6",
    "strategy": "CANARY",
    "config": {
      "initial_weight": 5,
      "increment": 10,
      "interval_seconds": 300,
      "max_weight": 100,
      "analysis": {
        "metrics": ["error_rate", "latency_p99", "saturation"],
        "thresholds": {
          "error_rate": { "max_increase_percent": 5 },
          "latency_p99": { "max_increase_percent": 20 }
        }
      },
      "auto_rollback": true
    }
  }
Response: 201
  {
    "deployment_id": "deploy_g7h8i9",
    "status": "PENDING",
    "strategy": "CANARY",
    "approval_required": true,
    "required_approvers": ["@platform-team"],
    "created_at": "2024-01-15T11:00:00Z"
  }

# Pipeline YAML Definition Example
# GET /api/v1/pipelines/{pipeline_id}/config
Response: 200
  {
    "config": "name: payment-service\n\ntriggers:\n  push:\n    branches: [main, 'release/*']\n  pull_request:\n    branches: [main]\n  schedule:\n    - cron: '0 2 * * *'\n\njobs:\n  lint:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - uses: actions/setup-node@v4\n        with: { node-version: 20 }\n      - run: npm ci\n      - run: npm run lint\n\n  test:\n    needs: [lint]\n    runs-on: ubuntu-latest\n    strategy:\n      matrix:\n        node-version: [18, 20, 22]\n        os: [ubuntu-latest, macos-latest]\n    steps:\n      - uses: actions/checkout@v4\n      - run: npm test\n\n  build:\n    needs: [test]\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - uses: docker/build-push-action@v5\n        with:\n          push: true\n          tags: registry.example.com/payment:${{ github.sha }}\n          cache-from: type=registry,ref=registry.example.com/payment:cache\n          cache-to: type=registry,ref=registry.example.com/payment:cache\n\n  deploy-staging:\n    needs: [build]\n    environment: staging\n    steps:\n      - uses: company/deploy-action@v2\n        with:\n          environment: staging\n          strategy: rolling\n          image: registry.example.com/payment:${{ github.sha }}\n\n  deploy-production:\n    needs: [deploy-staging]\n    environment: production\n    if: github.ref == 'refs/heads/main'\n    steps:\n      - uses: company/deploy-action@v2\n        with:\n          environment: production\n          strategy: canary\n          image: registry.example.com/payment:${{ github.sha }}"
  }
```

## 6. Deep Dive: Distributed Build Execution

### Job Scheduler

```python
import asyncio
from typing import List, Dict, Optional
from dataclasses import dataclass

@dataclass
class ResourceRequirements:
    cpu: float          # cores
    memory_mb: int
    gpu: int = 0
    disk_gb: int = 10

class JobScheduler:
    """
    Schedules jobs across worker pool with:
    - Resource-aware placement
    - Affinity rules (cache locality)
    - Priority queuing
    - Fair share across orgs
    """
    
    def __init__(self, redis, worker_registry):
        self.redis = redis
        self.workers = worker_registry
    
    async def schedule_job(self, job: Job) -> str:
        """Find best worker for a job and assign it."""
        requirements = self._compute_requirements(job)
        
        # 1. Find candidate workers with sufficient resources
        candidates = await self._find_eligible_workers(requirements)
        
        if not candidates:
            # No workers available - queue with priority
            score = self._compute_priority_score(job)
            await self.redis.zadd("queue:jobs:pending", {job.job_id: score})
            return "QUEUED"
        
        # 2. Score candidates (prefer cache locality)
        scored = []
        for worker in candidates:
            score = await self._score_worker(worker, job)
            scored.append((score, worker))
        
        scored.sort(reverse=True)
        best_worker = scored[0][1]
        
        # 3. Assign job to worker (atomic)
        assigned = await self._try_assign(best_worker, job)
        if not assigned:
            # Race condition - retry
            return await self.schedule_job(job)
        
        return best_worker.runner_id
    
    async def _score_worker(self, worker, job: Job) -> float:
        """
        Score a worker for a job. Higher = better fit.
        Factors: cache locality, resource utilization, zone affinity.
        """
        score = 0.0
        
        # Cache locality: does this worker have the build cache?
        cache_keys = self._get_cache_keys(job)
        for key in cache_keys:
            if await self.redis.sismember(f"worker:caches:{worker.runner_id}", key):
                score += 10.0  # Strong preference for cache-hot workers
        
        # Resource utilization: prefer workers with more headroom
        utilization = worker.cpu_used / worker.cpu_total
        score += (1.0 - utilization) * 5.0
        
        # Zone affinity: prefer same zone as artifact store
        if worker.zone == job.preferred_zone:
            score += 2.0
        
        return score
    
    async def _find_eligible_workers(self, req: ResourceRequirements) -> List:
        """Find workers with sufficient resources."""
        all_workers = await self.workers.get_active()
        eligible = []
        
        for w in all_workers:
            if (w.available_cpu >= req.cpu and 
                w.available_memory_mb >= req.memory_mb and
                w.available_gpu >= req.gpu and
                w.available_disk_gb >= req.disk_gb and
                w.status == 'READY'):
                eligible.append(w)
        
        return eligible


class WorkspaceManager:
    """
    Manages isolated workspaces for each job.
    Uses containers for complete isolation.
    """
    
    async def create_workspace(self, job: Job) -> Workspace:
        """
        Create an isolated workspace:
        1. Pull container image
        2. Mount workspace volume
        3. Inject secrets
        4. Setup networking
        """
        # 1. Resolve container image
        image = job.container_image or "ubuntu:22.04"
        await self.container_runtime.pull(image)
        
        # 2. Create workspace volume
        workspace_dir = f"/workspaces/{job.job_id}"
        
        # 3. Clone repository
        await self._git_clone(
            url=job.repo_url,
            ref=job.git_sha,
            target=workspace_dir,
            depth=1  # Shallow clone for speed
        )
        
        # 4. Restore build cache
        await self._restore_caches(job, workspace_dir)
        
        # 5. Create container
        container = await self.container_runtime.create(
            image=image,
            name=f"job-{job.job_id}",
            volumes={workspace_dir: '/workspace'},
            env=await self._resolve_env(job),
            network='job-network',  # Isolated network
            resources=ResourceLimits(
                cpu=job.resource_requirements.cpu,
                memory=f"{job.resource_requirements.memory_mb}m"
            ),
            security_opts=[
                'no-new-privileges',
                'seccomp=default'
            ]
        )
        
        return Workspace(container=container, path=workspace_dir)
    
    async def _resolve_env(self, job: Job) -> Dict[str, str]:
        """Resolve environment variables including secrets."""
        env = {
            'CI': 'true',
            'CI_JOB_ID': job.job_id,
            'CI_RUN_ID': job.run_id,
            'CI_COMMIT_SHA': job.git_sha,
            'CI_BRANCH': job.branch,
        }
        
        # Inject secrets from Vault
        for secret_ref in job.secrets:
            value = await self.vault.read_secret(secret_ref.vault_path)
            env[secret_ref.env_name] = value
        
        return env


class BuildCacheService:
    """
    Content-addressable build cache shared across runs.
    Supports: npm/yarn cache, Docker layer cache, compiled artifacts.
    """
    
    async def restore(self, key: str, paths: List[str], workspace: str) -> bool:
        """
        Restore cache by key.
        Key format: {type}-{hashFiles('**/package-lock.json')}
        """
        # 1. Look up in cache index
        cache_entry = await self.redis.hget(f"cache:index:{self.scope}", key)
        if not cache_entry:
            # Try prefix match for partial cache restore
            partial = await self._find_partial_match(key)
            if not partial:
                return False
            cache_entry = partial
        
        entry = json.loads(cache_entry)
        
        # 2. Download from content-addressable store
        archive_path = f"/tmp/cache-{key}.tar.zst"
        await self.s3.download(
            bucket='build-cache',
            key=entry['storage_path'],
            target=archive_path
        )
        
        # 3. Extract to workspace paths
        await self._extract(archive_path, workspace, paths)
        
        # 4. Update access time (LRU tracking)
        await self.redis.zadd(f"cache:lru:{self.scope}", {key: time.time()})
        
        return True
    
    async def save(self, key: str, paths: List[str], workspace: str):
        """Save paths to cache with content-addressing."""
        # 1. Create archive
        archive_path = f"/tmp/cache-{key}.tar.zst"
        await self._create_archive(workspace, paths, archive_path)
        
        # 2. Compute content hash
        content_hash = await self._hash_file(archive_path)
        
        # 3. Upload if not already in CAS
        storage_key = f"cas/{content_hash[:2]}/{content_hash}"
        if not await self.s3.exists('build-cache', storage_key):
            await self.s3.upload(archive_path, 'build-cache', storage_key)
        
        # 4. Update index
        await self.redis.hset(f"cache:index:{self.scope}", key, json.dumps({
            'storage_path': storage_key,
            'content_hash': content_hash,
            'size_bytes': os.path.getsize(archive_path),
            'created_at': datetime.utcnow().isoformat()
        }))
```

## 7. Deep Dive: Pipeline Engine (DAG Execution)

### DAG Resolution and Execution

```python
from collections import defaultdict, deque
from typing import Set

class PipelineEngine:
    """
    Executes pipeline as a DAG (Directed Acyclic Graph).
    Handles: dependencies, matrix expansion, conditionals, outputs.
    """
    
    def __init__(self, scheduler: JobScheduler, event_bus):
        self.scheduler = scheduler
        self.events = event_bus
    
    async def execute_pipeline(self, run: PipelineRun) -> None:
        """
        Main execution loop:
        1. Parse YAML → Job DAG
        2. Expand matrix strategies
        3. Execute in topological order respecting dependencies
        4. Propagate outputs between jobs
        """
        # 1. Parse pipeline config into job graph
        dag = self._build_dag(run.pipeline_config)
        
        # 2. Expand matrix strategies
        expanded_dag = self._expand_matrix(dag)
        
        # 3. Validate DAG (no cycles)
        if self._has_cycle(expanded_dag):
            raise PipelineError("Circular dependency detected in pipeline")
        
        # 4. Execute
        completed: Set[str] = set()
        failed: Set[str] = set()
        running: Dict[str, asyncio.Task] = {}
        
        while True:
            # Find ready jobs (all dependencies satisfied)
            ready = self._get_ready_jobs(expanded_dag, completed, failed, running)
            
            if not ready and not running:
                break  # All done
            
            # Launch ready jobs
            for job in ready:
                # Evaluate 'if' condition
                if not self._evaluate_condition(job, run, completed):
                    completed.add(job.job_id)
                    job.conclusion = 'SKIPPED'
                    continue
                
                # Resolve outputs from upstream jobs
                job.resolved_env = self._resolve_outputs(job, expanded_dag, completed)
                
                # Schedule and run
                task = asyncio.create_task(self._run_job(job))
                running[job.job_id] = task
            
            # Wait for any running job to complete
            if running:
                done, _ = await asyncio.wait(
                    running.values(),
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                for task in done:
                    job_id = next(k for k, v in running.items() if v == task)
                    del running[job_id]
                    
                    result = task.result()
                    if result.conclusion == 'SUCCESS':
                        completed.add(job_id)
                    else:
                        failed.add(job_id)
                        # Cancel downstream jobs if fail-fast
                        if run.pipeline_config.get('fail_fast', True):
                            await self._cancel_downstream(job_id, expanded_dag, running)
    
    def _expand_matrix(self, dag: Dict) -> Dict:
        """
        Expand matrix strategy into individual jobs.
        matrix:
          node-version: [18, 20, 22]
          os: [ubuntu, macos]
        Produces 6 jobs (3 × 2).
        """
        expanded = {}
        
        for job_id, job in dag.items():
            if job.get('strategy', {}).get('matrix'):
                matrix = job['strategy']['matrix']
                combinations = self._cartesian_product(matrix)
                
                for i, combo in enumerate(combinations):
                    new_id = f"{job_id}-{i}"
                    new_job = job.copy()
                    new_job['matrix_values'] = combo
                    new_job['name'] = f"{job['name']} ({', '.join(f'{k}={v}' for k,v in combo.items())})"
                    expanded[new_id] = new_job
            else:
                expanded[job_id] = job
        
        return expanded
    
    def _get_ready_jobs(self, dag, completed, failed, running) -> List:
        """Get jobs whose dependencies are all satisfied."""
        ready = []
        for job_id, job in dag.items():
            if job_id in completed or job_id in failed or job_id in running:
                continue
            
            deps = job.get('depends_on', [])
            if all(d in completed for d in deps):
                ready.append(job)
            elif any(d in failed for d in deps):
                # Dependency failed - skip this job
                failed.add(job_id)
        
        return ready
    
    def _resolve_outputs(self, job, dag, completed) -> Dict[str, str]:
        """
        Resolve output references from upstream jobs.
        Syntax: ${{ needs.build.outputs.image_tag }}
        """
        resolved = {}
        for dep_id in job.get('depends_on', []):
            dep_job = dag[dep_id]
            if dep_job.get('outputs'):
                for key, value in dep_job['outputs'].items():
                    resolved[f"needs.{dep_id}.outputs.{key}"] = value
        return resolved
    
    def _has_cycle(self, dag: Dict) -> bool:
        """Detect cycles using topological sort (Kahn's algorithm)."""
        in_degree = defaultdict(int)
        for job_id, job in dag.items():
            for dep in job.get('depends_on', []):
                in_degree[job_id] += 1
        
        queue = deque([j for j in dag if in_degree[j] == 0])
        visited = 0
        
        while queue:
            node = queue.popleft()
            visited += 1
            for job_id, job in dag.items():
                if node in job.get('depends_on', []):
                    in_degree[job_id] -= 1
                    if in_degree[job_id] == 0:
                        queue.append(job_id)
        
        return visited != len(dag)
```

## 8. Deep Dive: Deployment Orchestration

### Canary Deployment with Auto-Rollback

```python
import time
from typing import Dict, List

class CanaryDeploymentOrchestrator:
    """
    Progressive canary deployment with metric-based analysis.
    Steps: initial canary → monitor → increment → ... → full rollout or rollback.
    """
    
    async def execute_canary(self, deployment: Deployment) -> DeployResult:
        """
        Execute canary deployment with automated analysis.
        """
        config = deployment.config
        current_weight = 0
        target_weight = config['initial_weight']
        
        # 1. Deploy canary with initial weight
        await self._deploy_canary_version(deployment, target_weight)
        current_weight = target_weight
        
        # 2. Progressive rollout loop
        while current_weight < config['max_weight']:
            # Wait for analysis interval
            await asyncio.sleep(config['interval_seconds'])
            
            # Run metric analysis
            analysis = await self._analyze_metrics(deployment, config['analysis'])
            
            if analysis.verdict == 'FAIL':
                # Auto-rollback
                await self._rollback(deployment, analysis)
                return DeployResult(
                    status='ROLLED_BACK',
                    reason=f"Metric threshold breached: {analysis.failed_metrics}",
                    final_weight=current_weight
                )
            
            elif analysis.verdict == 'INCONCLUSIVE':
                # Extend analysis window (don't increment yet)
                continue
            
            # Analysis passed - increment canary weight
            current_weight = min(current_weight + config['increment'], config['max_weight'])
            await self._update_traffic_weight(deployment, current_weight)
            
            # Update progress
            await self._update_progress(deployment, {
                'current_weight': current_weight,
                'analysis_runs': analysis.run_count,
                'last_analysis': analysis.to_dict()
            })
        
        # 3. Full rollout - promote canary to primary
        await self._promote_canary(deployment)
        
        return DeployResult(status='COMPLETED', final_weight=100)
    
    async def _analyze_metrics(self, deployment: Deployment, 
                                analysis_config: dict) -> AnalysisResult:
        """
        Compare canary metrics against baseline.
        Uses sliding window over Prometheus/Datadog metrics.
        """
        metrics = analysis_config['metrics']
        thresholds = analysis_config['thresholds']
        
        failed_metrics = []
        
        for metric_name in metrics:
            # Get baseline (stable version) metric
            baseline = await self.metrics_client.query(
                metric=metric_name,
                labels={'deployment': 'stable', 'service': deployment.service_name},
                duration='5m'
            )
            
            # Get canary metric
            canary = await self.metrics_client.query(
                metric=metric_name,
                labels={'deployment': 'canary', 'service': deployment.service_name},
                duration='5m'
            )
            
            # Compare against threshold
            threshold = thresholds.get(metric_name, {})
            max_increase = threshold.get('max_increase_percent', 10)
            
            if baseline.value > 0:
                increase_percent = ((canary.value - baseline.value) / baseline.value) * 100
                
                if increase_percent > max_increase:
                    failed_metrics.append({
                        'metric': metric_name,
                        'baseline': baseline.value,
                        'canary': canary.value,
                        'increase_percent': increase_percent,
                        'threshold': max_increase
                    })
        
        if failed_metrics:
            return AnalysisResult(verdict='FAIL', failed_metrics=failed_metrics)
        
        # Check if we have enough data points for confidence
        if canary.sample_count < analysis_config.get('min_samples', 100):
            return AnalysisResult(verdict='INCONCLUSIVE')
        
        return AnalysisResult(verdict='PASS')
    
    async def _rollback(self, deployment: Deployment, analysis: AnalysisResult):
        """Execute rollback: shift all traffic back to stable."""
        # 1. Shift traffic to 0% canary immediately
        await self._update_traffic_weight(deployment, 0)
        
        # 2. Scale down canary pods
        await self.k8s.scale(
            deployment=f"{deployment.service_name}-canary",
            replicas=0,
            namespace=deployment.namespace
        )
        
        # 3. Update deployment status
        deployment.status = 'ROLLED_BACK'
        deployment.rolled_back_at = datetime.utcnow()
        deployment.rollback_reason = str(analysis.failed_metrics)
        await self.db.update_deployment(deployment)
        
        # 4. Notify
        await self.notifications.send(
            channel='slack',
            message=f"🔴 Canary rollback: {deployment.service_name}\n"
                    f"Reason: {analysis.failed_metrics}\n"
                    f"Traffic restored to stable version."
        )
    
    async def _deploy_canary_version(self, deployment: Deployment, weight: int):
        """Deploy canary version alongside stable."""
        # Create canary deployment
        await self.k8s.apply({
            'apiVersion': 'apps/v1',
            'kind': 'Deployment',
            'metadata': {
                'name': f"{deployment.service_name}-canary",
                'namespace': deployment.namespace,
                'labels': {'app': deployment.service_name, 'track': 'canary'}
            },
            'spec': {
                'replicas': max(1, int(deployment.stable_replicas * weight / 100)),
                'selector': {'matchLabels': {'app': deployment.service_name, 'track': 'canary'}},
                'template': {
                    'spec': {
                        'containers': [{
                            'name': 'app',
                            'image': deployment.new_image,
                        }]
                    }
                }
            }
        })
        
        # Configure traffic splitting (Istio VirtualService)
        await self.service_mesh.set_traffic_split(
            service=deployment.service_name,
            splits=[
                {'version': 'stable', 'weight': 100 - weight},
                {'version': 'canary', 'weight': weight}
            ]
        )
```

## 9. Component Optimization

### Worker Auto-Scaling

```yaml
# KEDA ScaledObject for worker scaling
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: ci-workers
spec:
  scaleTargetRef:
    name: ci-worker-pool
  minReplicaCount: 50
  maxReplicaCount: 2000
  triggers:
    - type: redis
      metadata:
        address: redis-cluster:6379
        listName: queue:jobs:pending
        listLength: "5"           # Scale up when >5 pending jobs per worker
    - type: cron
      metadata:
        timezone: America/New_York
        start: 0 8 * * 1-5       # Scale up for business hours
        end: 0 18 * * 1-5
        desiredReplicas: "500"
  advanced:
    horizontalPodAutoscalerConfig:
      behavior:
        scaleUp:
          stabilizationWindowSeconds: 15
          policies:
            - type: Percent
              value: 200
              periodSeconds: 15
        scaleDown:
          stabilizationWindowSeconds: 300
          policies:
            - type: Percent
              value: 10
              periodSeconds: 60
```

### Log Streaming Architecture

```python
class LogStreamService:
    """
    Real-time log streaming from workers to storage and UI.
    Handles 1M lines/second across all concurrent jobs.
    """
    
    async def stream_logs(self, job_id: str, lines: List[str]):
        """Buffer and batch log lines for efficiency."""
        # 1. Append to Kafka (durable, ordered)
        batch = [{
            'job_id': job_id,
            'line': line,
            'timestamp': datetime.utcnow().isoformat(),
            'line_number': self.counters[job_id]
        } for line in lines]
        self.counters[job_id] += len(lines)
        
        await self.kafka.produce_batch('build-logs', batch, key=job_id)
        
        # 2. Push to Redis pub/sub for live tail
        for entry in batch:
            await self.redis.publish(f"logs:live:{job_id}", json.dumps(entry))
    
    async def get_logs(self, job_id: str, offset: int = 0, limit: int = 1000) -> List:
        """Retrieve logs from storage (S3 after Kafka consumer persists)."""
        # Hot logs (recent): from Kafka consumer cache
        # Cold logs (completed jobs): from S3
        if await self._is_job_running(job_id):
            return await self._get_from_kafka(job_id, offset, limit)
        else:
            return await self._get_from_s3(job_id, offset, limit)
```

## 10. Observability

### Metrics

```yaml
metrics:
  - cicd.runs.triggered:             Counter (tags: pipeline, trigger_type)
  - cicd.runs.completed:             Counter (tags: pipeline, conclusion)
  - cicd.runs.duration_ms:           Histogram (tags: pipeline)
  - cicd.jobs.queued_time_ms:        Histogram (tags: pool)
  - cicd.jobs.execution_time_ms:     Histogram (tags: job_name, conclusion)
  - cicd.workers.utilization:        Gauge (tags: pool, worker_id)
  - cicd.workers.available:          Gauge (tags: pool)
  - cicd.cache.hit_rate:             Gauge (tags: cache_type)  # docker, deps, build
  - cicd.cache.restore_time_ms:      Histogram
  - cicd.artifacts.uploaded_bytes:    Counter (tags: pipeline)
  - cicd.deployments.total:          Counter (tags: environment, strategy, result)
  - cicd.deployments.rollbacks:      Counter (tags: environment, reason)
  - cicd.deployments.duration_ms:    Histogram (tags: strategy)
  - cicd.logs.lines_per_second:      Gauge
  - cicd.secrets.accessed:           Counter (tags: scope, secret_name)

alerts:
  - name: JobQueueBacklog
    condition: redis_zcard("queue:jobs:pending") > 500 for 5m
    severity: warning
  - name: WorkerPoolExhausted
    condition: cicd.workers.available == 0 for 2m
    severity: critical
  - name: DeploymentRollbackRate
    condition: rate(cicd.deployments.rollbacks) > 3/hour
    severity: critical
  - name: CacheHitRateLow
    condition: cicd.cache.hit_rate < 0.5 for 1h
    severity: warning
```

### Pipeline Trace

```
Trace: PipelineRun(run_id=run_a1b2c3, pipeline=payment-service)
├── [2ms]    Trigger: Webhook received (push to main)
├── [15ms]   Parse: YAML → DAG (4 jobs, 3 edges)
├── [5ms]    Expand: Matrix → 6 test variants
├── [3ms]    Queue: lint job dispatched
│
├── [45s]    Job: lint (worker-042)
│   ├── [3s]   Setup: Pull image + restore cache
│   ├── [40s]  Run: npm run lint
│   └── [2s]   Cleanup: Save cache
│
├── [180s]   Job: test (6 matrix variants, parallel)
│   ├── Worker-015: test (node=18, os=ubuntu) → SUCCESS (120s)
│   ├── Worker-023: test (node=20, os=ubuntu) → SUCCESS (115s)
│   ├── Worker-031: test (node=22, os=ubuntu) → SUCCESS (118s)
│   ├── Worker-044: test (node=18, os=macos)  → SUCCESS (150s)
│   ├── Worker-052: test (node=20, os=macos)  → SUCCESS (145s)
│   └── Worker-067: test (node=22, os=macos)  → SUCCESS (180s)
│
├── [90s]    Job: build (worker-089)
│   ├── [5s]   Docker: Layer cache restore (HIT 12/15 layers)
│   ├── [60s]  Docker: Build (3 layers rebuilt)
│   ├── [20s]  Docker: Push to registry
│   └── [5s]   Artifact: Record image digest
│
└── [600s]   Job: deploy-staging (canary)
    ├── [30s]  Deploy: Canary at 5%
    ├── [300s] Monitor: Metrics analysis (5 iterations)
    ├── [30s]  Increment: 5% → 25% → 50% → 75% → 100%
    └── [10s]  Promote: Canary → Stable

Total: 915s (15.25 minutes) ✓
```

## 11. Considerations

### Trade-offs
| Decision | Chosen | Alternative | Rationale |
|----------|--------|-------------|-----------|
| Job isolation | Containers (Docker) | VMs / Firecracker | Balance of isolation vs startup time; containers start in <2s |
| Build cache | Content-addressable (S3) | Distributed filesystem | Deduplication, immutable, no consistency issues |
| Pipeline format | YAML DSL | GUI-only / Groovy (Jenkins) | Version-controllable, readable, widely adopted |
| Deployment analysis | Metric-based (Prometheus) | Traffic replay / Chaos | Real-time, non-invasive, automated decision |
| Log storage | Kafka → S3 | Direct to ES | Cost effective at scale, separate hot/cold paths |

### Security
- **Secret isolation**: Secrets injected as env vars, never written to disk/logs
- **Log masking**: Auto-detect and redact secrets appearing in logs
- **Supply chain**: Verify action signatures, pin dependencies by SHA
- **Network isolation**: Jobs can't communicate with each other
- **Ephemeral workspaces**: Destroyed after job completion, no state leak

### Failure Handling
- **Worker crash mid-job**: Heartbeat timeout → reschedule on different worker
- **Cache corruption**: Content hash verification on restore, rebuild on mismatch
- **Deployment failure**: Auto-rollback within defined threshold
- **Queue overflow**: Back-pressure on triggers, priority queue favors production deploys
- **Circular dependencies**: Detected at parse time, pipeline rejected before execution

### Cost Optimization
- Spot instances for non-urgent builds (80% savings)
- Build cache sharing saves ~40% of build time fleet-wide
- Auto-scale to zero during off-hours (save 60% compute)
- Artifact lifecycle policies: delete intermediate artifacts after 7 days
- Log compression + tiering: hot (1 day) → warm (7 days) → cold (90 days)
