# CI/CD, GitHub Actions & Runners - Complete Guide

## 1. CI/CD Fundamentals

### Continuous Integration (CI)
- Developers merge code to main branch **frequently** (multiple times/day)
- Every merge triggers automated **build and test**
- Fast feedback loop: broken code caught within minutes
- Key practices:
  - Single source repository
  - Automated build process
  - Self-testing builds
  - Every commit builds on integration machine
  - Fix broken builds immediately
  - Keep the build fast (<10 minutes ideal)

### Continuous Delivery (CD)
- Code is **always in a deployable state**
- Release to production requires **manual approval** (button click)
- Extends CI with deployment automation to staging/pre-prod
- Confidence: any commit could go to production

### Continuous Deployment
- Every change that passes automated tests goes to **production automatically**
- No human intervention between commit and deploy
- Requires robust test suite and monitoring
- Most aggressive form of CI/CD

### CI/CD Pipeline Stages

```
Source → Build → Test → Package → Deploy (Staging) → Deploy (Production)
```

| Stage | Purpose | Tools |
|-------|---------|-------|
| Source | Code change trigger | Git push, PR, tag |
| Build | Compile, transpile | npm build, gradle, docker build |
| Test | Validate correctness | Jest, pytest, Selenium |
| Package | Create artifact | Docker image, JAR, ZIP |
| Deploy | Release to environment | kubectl, aws ecs, terraform |

### Benefits of CI/CD
- **Faster feedback**: know within minutes if code is broken
- **Fewer bugs in production**: caught early in pipeline
- **Consistent deployments**: same process every time
- **Reduced risk**: small changes, easy to rollback
- **Higher developer productivity**: less time on manual processes
- **Faster time to market**: release multiple times per day

### CI/CD Anti-Patterns
- Long-running feature branches (merge conflicts, big bang integration)
- Skipping tests to "save time"
- Manual steps in the pipeline
- Deploying on Friday afternoon
- No rollback strategy
- Testing only in production
- Shared mutable infrastructure for CI
- Not monitoring post-deployment

---

## 2. GitHub Actions Overview

### What is GitHub Actions?
- CI/CD platform **built into GitHub** (no external service needed)
- Event-driven automation: respond to any GitHub event
- Supports any language, platform, cloud
- Marketplace with 15,000+ community actions

### Core Components

| Component | Description |
|-----------|-------------|
| **Workflow** | Automated process defined in YAML, triggered by events |
| **Event** | Activity that triggers a workflow (push, PR, schedule) |
| **Job** | Set of steps running on the same runner |
| **Step** | Individual task (run command or use action) |
| **Action** | Reusable unit of code (marketplace or custom) |
| **Runner** | Server that executes workflows |

### Pricing (as of 2024)

| Plan | Free Minutes/Month | Storage |
|------|-------------------|---------|
| Free | 2,000 | 500 MB |
| Pro | 3,000 | 1 GB |
| Team | 3,000 | 2 GB |
| Enterprise | 50,000 | 50 GB |

**Minute multipliers** (cost more on non-Linux):
- Linux: 1x
- Windows: 2x
- macOS: 10x

### Workflow File Location
```
.github/workflows/ci.yml
.github/workflows/deploy.yml
.github/workflows/release.yml
```

---

## 3. GitHub Actions Workflow Syntax (Detailed)

### Basic Workflow Structure

```yaml
name: CI Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: npm ci
      - run: npm test
      - run: npm run build
```

### Events (Triggers)

```yaml
on:
  # Push to specific branches/tags
  push:
    branches: [main, 'release/**']
    tags: ['v*']
    paths: ['src/**', 'package.json']
    paths-ignore: ['docs/**', '**.md']

  # Pull request events
  pull_request:
    branches: [main]
    types: [opened, synchronize, reopened]

  # Scheduled (cron)
  schedule:
    - cron: '0 2 * * 1-5'  # Weekdays at 2 AM UTC

  # Manual trigger
  workflow_dispatch:
    inputs:
      environment:
        description: 'Deployment environment'
        required: true
        type: choice
        options: [dev, staging, production]
      debug:
        description: 'Enable debug mode'
        type: boolean
        default: false

  # API trigger
  repository_dispatch:
    types: [deploy-command]

  # Release events
  release:
    types: [published, created]

  # Reusable workflow (called by another workflow)
  workflow_call:
    inputs:
      environment:
        required: true
        type: string
    secrets:
      deploy_key:
        required: true

  # Issue/PR comments
  issue_comment:
    types: [created]
```

### Jobs Configuration

```yaml
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm run lint

  test:
    runs-on: ubuntu-latest
    needs: lint  # depends on lint job
    strategy:
      matrix:
        node-version: [18, 20, 22]
      fail-fast: false
      max-parallel: 3
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: ${{ matrix.node-version }}
      - run: npm ci
      - run: npm test

  deploy:
    runs-on: ubuntu-latest
    needs: [lint, test]  # depends on multiple jobs
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    environment: production
    permissions:
      id-token: write
      contents: read
    steps:
      - run: echo "Deploying..."

  # Job with service containers
  integration-test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_DB: testdb
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7
        ports:
          - 6379:6379
    container:
      image: node:20
    steps:
      - uses: actions/checkout@v4
      - run: npm ci
      - run: npm run test:integration
        env:
          DATABASE_URL: postgres://postgres:test@postgres:5432/testdb
          REDIS_URL: redis://redis:6379
```

### Steps Configuration

```yaml
steps:
  - name: Checkout code
    uses: actions/checkout@v4
    with:
      fetch-depth: 0  # full history for versioning

  - name: Run tests
    id: test-step
    run: |
      npm test 2>&1 | tee test-output.txt
      echo "coverage=$(cat coverage/coverage-summary.json | jq '.total.lines.pct')" >> $GITHUB_OUTPUT
    env:
      CI: true
      NODE_ENV: test
    continue-on-error: true
    timeout-minutes: 15

  - name: Check test result
    if: steps.test-step.outcome == 'failure'
    run: echo "Tests failed!" && exit 1

  - name: Conditional step
    if: |
      github.event_name == 'push' &&
      contains(github.event.head_commit.message, '[deploy]')
    run: echo "Deploy triggered by commit message"
```

### Expressions and Contexts

```yaml
env:
  BRANCH_NAME: ${{ github.head_ref || github.ref_name }}
  IS_MAIN: ${{ github.ref == 'refs/heads/main' }}
  PR_NUMBER: ${{ github.event.pull_request.number }}

jobs:
  example:
    runs-on: ubuntu-latest
    outputs:
      version: ${{ steps.version.outputs.value }}
    steps:
      - id: version
        run: echo "value=1.2.3" >> $GITHUB_OUTPUT

      # Using expressions
      - run: echo "${{ secrets.API_KEY }}"
      - run: echo "${{ env.BRANCH_NAME }}"
      - run: echo "${{ matrix.os }}"
      - run: echo "${{ needs.build.outputs.version }}"
      - run: echo "${{ runner.os }}"
      - run: echo "${{ github.actor }}"
      - run: echo "${{ github.sha }}"
      - run: echo "${{ github.run_number }}"

      # Functions
      - if: contains(github.event.pull_request.labels.*.name, 'deploy')
        run: echo "Has deploy label"
      - if: startsWith(github.ref, 'refs/tags/v')
        run: echo "Tag push"
      - if: always()  # run even if previous steps fail
        run: echo "Cleanup"
      - if: failure()  # run only on failure
        run: echo "Send alert"
      - if: cancelled()
        run: echo "Was cancelled"
```

---

## 4. GitHub Actions - Actions Deep Dive

### Essential Marketplace Actions

```yaml
# Checkout repository
- uses: actions/checkout@v4
  with:
    fetch-depth: 0
    token: ${{ secrets.PAT }}  # for private submodules

# Setup runtimes
- uses: actions/setup-node@v4
  with:
    node-version: '20'
    cache: 'npm'
- uses: actions/setup-python@v5
  with:
    python-version: '3.12'
- uses: actions/setup-go@v5
  with:
    go-version: '1.22'
- uses: actions/setup-java@v4
  with:
    distribution: 'temurin'
    java-version: '21'

# Caching
- uses: actions/cache@v4
  with:
    path: ~/.npm
    key: ${{ runner.os }}-node-${{ hashFiles('**/package-lock.json') }}
    restore-keys: |
      ${{ runner.os }}-node-

# Artifacts
- uses: actions/upload-artifact@v4
  with:
    name: build-output
    path: dist/
    retention-days: 5
- uses: actions/download-artifact@v4
  with:
    name: build-output
    path: dist/

# Docker
- uses: docker/setup-buildx-action@v3
- uses: docker/login-action@v3
  with:
    registry: ghcr.io
    username: ${{ github.actor }}
    password: ${{ secrets.GITHUB_TOKEN }}
- uses: docker/build-push-action@v5
  with:
    push: true
    tags: ghcr.io/${{ github.repository }}:${{ github.sha }}
    cache-from: type=gha
    cache-to: type=gha,mode=max

# AWS
- uses: aws-actions/configure-aws-credentials@v4
  with:
    role-to-assume: arn:aws:iam::123456789:role/github-actions
    aws-region: us-east-1
```

### Action Types

**JavaScript Action** (fast, runs directly on runner):
```yaml
# action.yml
name: 'My JS Action'
description: 'Does something'
inputs:
  name:
    description: 'Name input'
    required: true
    default: 'World'
outputs:
  result:
    description: 'The result'
runs:
  using: 'node20'
  main: 'dist/index.js'
```

**Docker Container Action** (any language, isolated):
```yaml
# action.yml
name: 'My Docker Action'
description: 'Runs in container'
inputs:
  args:
    required: true
runs:
  using: 'docker'
  image: 'Dockerfile'
  args:
    - ${{ inputs.args }}
```

**Composite Action** (reuse steps):
```yaml
# .github/actions/setup-project/action.yml
name: 'Setup Project'
description: 'Common setup steps'
inputs:
  node-version:
    default: '20'
runs:
  using: 'composite'
  steps:
    - uses: actions/setup-node@v4
      with:
        node-version: ${{ inputs.node-version }}
        cache: 'npm'
    - run: npm ci
      shell: bash
    - run: npm run build
      shell: bash
```

Usage:
```yaml
steps:
  - uses: actions/checkout@v4
  - uses: ./.github/actions/setup-project
    with:
      node-version: '20'
```

### Versioning Actions
```yaml
# Pinned to major version (recommended for third-party)
- uses: actions/checkout@v4

# Pinned to exact SHA (most secure)
- uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11

# Branch reference (not recommended for production)
- uses: actions/checkout@main
```

---

## 5. GitHub Actions Advanced Features

### Matrix Strategy

```yaml
jobs:
  test:
    strategy:
      fail-fast: false
      max-parallel: 4
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
        node: [18, 20, 22]
        include:
          - os: ubuntu-latest
            node: 20
            coverage: true
        exclude:
          - os: macos-latest
            node: 18
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: ${{ matrix.node }}
      - run: npm ci
      - run: npm test
      - if: matrix.coverage
        run: npm run coverage
```

### Secrets Management

```yaml
# Repository secret
- run: echo "${{ secrets.API_KEY }}"

# Environment secret (override repo-level)
jobs:
  deploy:
    environment: production
    steps:
      - run: deploy --key "${{ secrets.PROD_API_KEY }}"

# GITHUB_TOKEN (automatic, scoped to repo)
- uses: actions/github-script@v7
  with:
    github-token: ${{ secrets.GITHUB_TOKEN }}
    script: |
      await github.rest.issues.createComment({
        owner: context.repo.owner,
        repo: context.repo.repo,
        issue_number: context.issue.number,
        body: 'CI passed!'
      })
```

### Environments with Protection Rules

```yaml
jobs:
  deploy-staging:
    environment: staging
    runs-on: ubuntu-latest
    steps:
      - run: deploy-to-staging.sh

  deploy-production:
    needs: deploy-staging
    environment:
      name: production
      url: https://myapp.com
    runs-on: ubuntu-latest
    steps:
      - run: deploy-to-prod.sh
```

Environment settings (configured in GitHub UI):
- **Required reviewers**: 1-6 people must approve
- **Wait timer**: delay in minutes (0-43200)
- **Deployment branches**: restrict which branches can deploy
- **Environment secrets**: secrets scoped to this environment

### Caching

```yaml
- uses: actions/cache@v4
  id: cache-deps
  with:
    path: |
      node_modules
      ~/.cache/Cypress
    key: deps-${{ runner.os }}-${{ hashFiles('package-lock.json') }}
    restore-keys: |
      deps-${{ runner.os }}-

- if: steps.cache-deps.outputs.cache-hit != 'true'
  run: npm ci
```

### Concurrency

```yaml
# Cancel previous runs for same branch
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

# Per-environment concurrency (don't cancel deploys)
jobs:
  deploy:
    concurrency:
      group: deploy-production
      cancel-in-progress: false
```

### Reusable Workflows

**Reusable workflow definition** (`.github/workflows/reusable-deploy.yml`):
```yaml
name: Reusable Deploy

on:
  workflow_call:
    inputs:
      environment:
        required: true
        type: string
      image-tag:
        required: true
        type: string
    secrets:
      aws-role-arn:
        required: true
    outputs:
      deploy-url:
        description: "Deployment URL"
        value: ${{ jobs.deploy.outputs.url }}

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: ${{ inputs.environment }}
    outputs:
      url: ${{ steps.deploy.outputs.url }}
    steps:
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.aws-role-arn }}
          aws-region: us-east-1
      - id: deploy
        run: |
          # deploy logic
          echo "url=https://${{ inputs.environment }}.myapp.com" >> $GITHUB_OUTPUT
```

**Calling the reusable workflow**:
```yaml
jobs:
  deploy-staging:
    uses: ./.github/workflows/reusable-deploy.yml
    with:
      environment: staging
      image-tag: ${{ github.sha }}
    secrets:
      aws-role-arn: ${{ secrets.AWS_ROLE_STAGING }}

  deploy-prod:
    needs: deploy-staging
    uses: ./.github/workflows/reusable-deploy.yml
    with:
      environment: production
      image-tag: ${{ github.sha }}
    secrets:
      aws-role-arn: ${{ secrets.AWS_ROLE_PROD }}
```

### OIDC for Cloud Authentication (No Stored Secrets)

```yaml
permissions:
  id-token: write
  contents: read

steps:
  # AWS
  - uses: aws-actions/configure-aws-credentials@v4
    with:
      role-to-assume: arn:aws:iam::123456789012:role/GitHubActionsRole
      aws-region: us-east-1
      # No access keys needed!

  # Azure
  - uses: azure/login@v2
    with:
      client-id: ${{ secrets.AZURE_CLIENT_ID }}
      tenant-id: ${{ secrets.AZURE_TENANT_ID }}
      subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}

  # GCP
  - uses: google-github-actions/auth@v2
    with:
      workload_identity_provider: projects/123/locations/global/workloadIdentityPools/pool/providers/github
      service_account: my-sa@project.iam.gserviceaccount.com
```

### Workflow Commands

```yaml
- run: |
    # Set output
    echo "version=1.0.0" >> $GITHUB_OUTPUT

    # Set environment variable for subsequent steps
    echo "MY_VAR=value" >> $GITHUB_ENV

    # Add to PATH
    echo "/custom/bin" >> $GITHUB_PATH

    # Logging commands
    echo "::debug::Debug message"
    echo "::warning file=app.js,line=1::Warning message"
    echo "::error file=app.js,line=10::Error message"

    # Grouping
    echo "::group::Install dependencies"
    npm ci
    echo "::endgroup::"

    # Masking secrets
    echo "::add-mask::$DYNAMIC_SECRET"

    # Job summary
    echo "## Build Results" >> $GITHUB_STEP_SUMMARY
    echo "| Test | Result |" >> $GITHUB_STEP_SUMMARY
    echo "| --- | --- |" >> $GITHUB_STEP_SUMMARY
    echo "| Unit | ✅ |" >> $GITHUB_STEP_SUMMARY
```

---

## 6. Runners

### GitHub-Hosted Runners

| Runner | OS | vCPU | RAM | Storage |
|--------|-----|------|-----|---------|
| `ubuntu-latest` | Ubuntu 22.04 | 4 | 16 GB | 14 GB SSD |
| `windows-latest` | Windows Server 2022 | 4 | 16 GB | 14 GB SSD |
| `macos-latest` | macOS 14 (Sonoma) | 3 (M1) | 7 GB | 14 GB SSD |
| `macos-13` | macOS 13 (Ventura) | 4 (Intel) | 14 GB | 14 GB SSD |

**Preinstalled tools** (ubuntu-latest): Docker, Node.js, Python, Java, Go, .NET, aws-cli, az-cli, gcloud, kubectl, terraform, helm, and many more.

### Self-Hosted Runners

**Why use self-hosted?**
- Custom hardware (GPU, ARM, high memory)
- Network access to internal resources (VPN, private subnets)
- Cost savings at scale (>50,000 minutes/month)
- Specialized/licensed tools
- Compliance requirements (data residency)
- Faster builds (persistent caches, no cold start)

**Setup:**
```bash
# Download
mkdir actions-runner && cd actions-runner
curl -o actions-runner-linux-x64-2.311.0.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.311.0/actions-runner-linux-x64-2.311.0.tar.gz
tar xzf ./actions-runner-linux-x64-2.311.0.tar.gz

# Configure
./config.sh --url https://github.com/ORG/REPO \
  --token AXXXXXX \
  --labels gpu,linux,x64 \
  --runnergroup default

# Run as service
sudo ./svc.sh install
sudo ./svc.sh start
```

**Using self-hosted runner:**
```yaml
jobs:
  build:
    runs-on: [self-hosted, linux, gpu]
    steps:
      - uses: actions/checkout@v4
      - run: nvidia-smi
      - run: python train_model.py
```

**Labels and targeting:**
```yaml
runs-on: [self-hosted, linux, x64, gpu]  # ALL labels must match
```

**Runner Groups** (Organization level):
- Group runners by purpose (production, testing, GPU)
- Restrict which repositories can use which groups
- Set permissions at organization level

### Security Considerations for Self-Hosted

> **WARNING**: Do NOT use self-hosted runners with public repositories. Any fork can create a PR that executes arbitrary code on your runner.

Mitigations:
- Use only with private repositories
- Use ephemeral runners (fresh VM per job)
- Network isolation (separate VPC/subnet)
- Don't store secrets on runner machines
- Use runner groups to restrict access
- Regular security patching

### Larger Runners (GitHub-hosted)

```yaml
runs-on: ubuntu-latest-4-cores   # 4 vCPU
runs-on: ubuntu-latest-8-cores   # 8 vCPU
runs-on: ubuntu-latest-16-cores  # 16 vCPU
runs-on: ubuntu-latest-32-cores  # 32 vCPU
runs-on: ubuntu-latest-64-cores  # 64 vCPU

# GPU runners (preview)
runs-on: ubuntu-latest-gpu-t4    # NVIDIA T4
```

### Ephemeral Runners

```bash
# Configure as ephemeral (destroyed after single job)
./config.sh --url https://github.com/ORG/REPO \
  --token TOKEN \
  --ephemeral
```

Benefits:
- Clean environment every job (no state leakage)
- Better security (no persistent compromises)
- Required for untrusted workloads

### Actions Runner Controller (ARC) - Kubernetes Auto-Scaling

```yaml
# runner-deployment.yaml
apiVersion: actions.summerwind.dev/v1alpha1
kind: RunnerDeployment
metadata:
  name: github-runner
spec:
  replicas: 3
  template:
    spec:
      repository: my-org/my-repo
      labels:
        - k8s
        - linux
      ephemeral: true
---
apiVersion: actions.summerwind.dev/v1alpha1
kind: HorizontalRunnerAutoscaler
metadata:
  name: github-runner-autoscaler
spec:
  scaleTargetRef:
    name: github-runner
  minReplicas: 1
  maxReplicas: 20
  scaleUpTriggers:
    - githubEvent:
        workflowJob: {}
      duration: "30m"
  scaleDownDelaySecondsAfterScaleOut: 300
```

---

## 7. CI/CD Pipeline Patterns with GitHub Actions

### Basic CI Pipeline

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  ci:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
      - run: npm ci
      - run: npm run lint
      - run: npm run typecheck
      - run: npm test -- --coverage
      - run: npm run build
      - uses: actions/upload-artifact@v4
        with:
          name: coverage
          path: coverage/
```

### Docker CI/CD Pipeline

```yaml
name: Docker CI/CD

on:
  push:
    branches: [main]
    tags: ['v*']

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
      id-token: write
    steps:
      - uses: actions/checkout@v4

      - uses: docker/setup-qemu-action@v3
      - uses: docker/setup-buildx-action@v3

      - uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=ref,event=branch
            type=semver,pattern={{version}}
            type=sha

      - uses: docker/build-push-action@v5
        with:
          context: .
          platforms: linux/amd64,linux/arm64
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  scan:
    needs: build-and-push
    runs-on: ubuntu-latest
    steps:
      - uses: aquasecurity/trivy-action@master
        with:
          image-ref: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:sha-${{ github.sha }}
          format: 'sarif'
          output: 'trivy-results.sarif'
      - uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: 'trivy-results.sarif'

  deploy:
    needs: scan
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: production
    steps:
      - run: echo "Deploy image with tag sha-${{ github.sha }}"
```

### Multi-Environment Promotion

```yaml
name: Deploy Pipeline

on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    outputs:
      image-tag: ${{ steps.build.outputs.tag }}
    steps:
      - uses: actions/checkout@v4
      - id: build
        run: |
          TAG="sha-${GITHUB_SHA::8}"
          docker build -t myapp:$TAG .
          echo "tag=$TAG" >> $GITHUB_OUTPUT

  deploy-dev:
    needs: build
    runs-on: ubuntu-latest
    environment: development
    steps:
      - run: echo "Deploying ${{ needs.build.outputs.image-tag }} to dev"

  deploy-staging:
    needs: deploy-dev
    runs-on: ubuntu-latest
    environment: staging  # may have wait timer
    steps:
      - run: echo "Deploying to staging"
      - run: npm run test:smoke -- --url https://staging.myapp.com

  deploy-production:
    needs: deploy-staging
    runs-on: ubuntu-latest
    environment: production  # requires manual approval
    steps:
      - run: echo "Deploying to production"
```

### Monorepo Pipeline

```yaml
name: Monorepo CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  changes:
    runs-on: ubuntu-latest
    outputs:
      api: ${{ steps.filter.outputs.api }}
      web: ${{ steps.filter.outputs.web }}
      shared: ${{ steps.filter.outputs.shared }}
    steps:
      - uses: actions/checkout@v4
      - uses: dorny/paths-filter@v3
        id: filter
        with:
          filters: |
            api:
              - 'packages/api/**'
              - 'packages/shared/**'
            web:
              - 'packages/web/**'
              - 'packages/shared/**'
            shared:
              - 'packages/shared/**'

  api:
    needs: changes
    if: needs.changes.outputs.api == 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: cd packages/api && npm ci && npm test

  web:
    needs: changes
    if: needs.changes.outputs.web == 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: cd packages/web && npm ci && npm test && npm run build
```

### Infrastructure Pipeline (Terraform)

```yaml
name: Terraform

on:
  push:
    branches: [main]
    paths: ['infra/**']
  pull_request:
    paths: ['infra/**']

permissions:
  id-token: write
  contents: read
  pull-requests: write

jobs:
  plan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
          aws-region: us-east-1

      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: 1.7.0

      - run: terraform init
        working-directory: infra/

      - run: terraform plan -out=plan.tfplan -no-color
        id: plan
        working-directory: infra/

      - uses: actions/github-script@v7
        if: github.event_name == 'pull_request'
        with:
          script: |
            const output = `#### Terraform Plan
            \`\`\`
            ${{ steps.plan.outputs.stdout }}
            \`\`\`
            `;
            github.rest.issues.createComment({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: context.issue.number,
              body: output
            });

  apply:
    needs: plan
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    runs-on: ubuntu-latest
    environment: infrastructure
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
          aws-region: us-east-1
      - uses: hashicorp/setup-terraform@v3
      - run: terraform init && terraform apply -auto-approve
        working-directory: infra/
```

### Release Workflow

```yaml
name: Release

on:
  push:
    tags: ['v*']

permissions:
  contents: write
  packages: write

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Generate changelog
        id: changelog
        run: |
          PREV_TAG=$(git describe --tags --abbrev=0 HEAD^ 2>/dev/null || echo "")
          if [ -n "$PREV_TAG" ]; then
            CHANGES=$(git log $PREV_TAG..HEAD --pretty=format:"- %s (%h)" --no-merges)
          else
            CHANGES=$(git log --pretty=format:"- %s (%h)" --no-merges)
          fi
          echo "changes<<EOF" >> $GITHUB_OUTPUT
          echo "$CHANGES" >> $GITHUB_OUTPUT
          echo "EOF" >> $GITHUB_OUTPUT

      - uses: softprops/action-gh-release@v2
        with:
          body: |
            ## Changes
            ${{ steps.changelog.outputs.changes }}
          generate_release_notes: true
```

---

## 8. Testing in CI/CD

### Unit Tests

```yaml
- run: npm test -- --ci --coverage --maxWorkers=50%
  env:
    CI: true
```

### Integration Tests with Services

```yaml
jobs:
  integration:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test
        ports: ['5432:5432']
        options: --health-cmd pg_isready --health-interval 10s --health-timeout 5s --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - run: npm ci
      - run: npx prisma migrate deploy
        env:
          DATABASE_URL: postgresql://postgres:test@localhost:5432/test
      - run: npm run test:integration
```

### E2E Tests (Playwright)

```yaml
jobs:
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: npm ci
      - run: npx playwright install --with-deps
      - run: npm run build
      - run: npx playwright test
        env:
          BASE_URL: http://localhost:3000
      - uses: actions/upload-artifact@v4
        if: failure()
        with:
          name: playwright-report
          path: playwright-report/
```

### Security Testing

```yaml
jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      # SAST with CodeQL
      - uses: actions/checkout@v4
      - uses: github/codeql-action/init@v3
        with:
          languages: javascript
      - uses: github/codeql-action/analyze@v3

      # Dependency scanning
      - run: npm audit --audit-level=high

      # Container scanning
      - uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          severity: 'CRITICAL,HIGH'
```

### Test Parallelization

```yaml
jobs:
  test:
    strategy:
      matrix:
        shard: [1, 2, 3, 4]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci
      - run: npx playwright test --shard=${{ matrix.shard }}/4
```

### Flaky Test Handling

```yaml
- run: |
    for i in 1 2 3; do
      npm test && break || {
        echo "Attempt $i failed, retrying..."
        sleep 5
      }
    done
```

---

## 9. Deployment Strategies with GitHub Actions

### AWS ECS Deployment

```yaml
jobs:
  deploy-ecs:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: actions/checkout@v4

      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
          aws-region: us-east-1

      - uses: aws-actions/amazon-ecr-login@v2
        id: ecr

      - run: |
          docker build -t ${{ steps.ecr.outputs.registry }}/myapp:${{ github.sha }} .
          docker push ${{ steps.ecr.outputs.registry }}/myapp:${{ github.sha }}

      - id: task-def
        uses: aws-actions/amazon-ecs-render-task-definition@v1
        with:
          task-definition: task-definition.json
          container-name: app
          image: ${{ steps.ecr.outputs.registry }}/myapp:${{ github.sha }}

      - uses: aws-actions/amazon-ecs-deploy-task-definition@v2
        with:
          task-definition: ${{ steps.task-def.outputs.task-definition }}
          service: my-service
          cluster: my-cluster
          wait-for-service-stability: true
```

### Kubernetes (EKS) Deployment

```yaml
jobs:
  deploy-eks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
          aws-region: us-east-1

      - run: aws eks update-kubeconfig --name my-cluster

      - run: |
          helm upgrade --install myapp ./helm/myapp \
            --set image.tag=${{ github.sha }} \
            --set replicas=3 \
            --wait --timeout 300s
```

### Blue/Green Deployment

```yaml
jobs:
  blue-green:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to green
        run: |
          aws ecs update-service --cluster prod \
            --service green-service \
            --task-definition myapp:${{ github.run_number }}
          aws ecs wait services-stable --cluster prod --services green-service

      - name: Health check green
        run: |
          for i in $(seq 1 30); do
            STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://green.myapp.com/health)
            [ "$STATUS" = "200" ] && exit 0
            sleep 10
          done
          exit 1

      - name: Switch traffic
        run: |
          aws elbv2 modify-listener --listener-arn $LISTENER_ARN \
            --default-actions Type=forward,TargetGroupArn=$GREEN_TG_ARN
```

### Canary Deployment

```yaml
jobs:
  canary:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy canary (10%)
        run: |
          kubectl set image deployment/myapp-canary app=myapp:${{ github.sha }}
          kubectl scale deployment/myapp-canary --replicas=1

      - name: Monitor canary (5 min)
        run: |
          sleep 300
          ERROR_RATE=$(curl -s "http://prometheus:9090/api/v1/query?query=rate(http_errors_total{deployment='canary'}[5m])")
          if (( $(echo "$ERROR_RATE > 0.01" | bc -l) )); then
            echo "Error rate too high, rolling back"
            kubectl scale deployment/myapp-canary --replicas=0
            exit 1
          fi

      - name: Full rollout
        run: |
          kubectl set image deployment/myapp app=myapp:${{ github.sha }}
          kubectl rollout status deployment/myapp --timeout=300s
          kubectl scale deployment/myapp-canary --replicas=0
```

### Rollback Strategy

```yaml
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy
        id: deploy
        run: |
          PREV_TASK=$(aws ecs describe-services --cluster prod --services myapp \
            --query 'services[0].taskDefinition' --output text)
          echo "previous-task=$PREV_TASK" >> $GITHUB_OUTPUT
          # deploy new version...

      - name: Health check
        id: health
        continue-on-error: true
        run: |
          sleep 60
          curl -f https://myapp.com/health

      - name: Rollback on failure
        if: steps.health.outcome == 'failure'
        run: |
          aws ecs update-service --cluster prod --service myapp \
            --task-definition ${{ steps.deploy.outputs.previous-task }}
          aws ecs wait services-stable --cluster prod --services myapp
          echo "::error::Deployment failed, rolled back to previous version"
          exit 1
```

---

## 10. Security Best Practices

### Secrets Management
```yaml
# GOOD: OIDC (no stored secrets)
permissions:
  id-token: write
- uses: aws-actions/configure-aws-credentials@v4
  with:
    role-to-assume: arn:aws:iam::123:role/role

# GOOD: Minimal scope secrets
- run: deploy.sh
  env:
    DB_PASSWORD: ${{ secrets.DB_PASSWORD }}

# BAD: Never do this
- run: echo ${{ secrets.TOKEN }}  # exposed in logs
```

### Minimal Permissions

```yaml
# Global permissions (restrictive)
permissions:
  contents: read

jobs:
  deploy:
    permissions:
      contents: read
      id-token: write
      packages: write
```

### Dependency Pinning

```yaml
# Pin actions to SHA (prevent supply chain attacks)
- uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11  # v4.1.1

# Use Dependabot for action updates
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
```

### Branch Protection
- Require PR reviews before merge
- Require status checks to pass
- Require signed commits
- Restrict who can push to main
- CODEOWNERS for `.github/workflows/`

```
# .github/CODEOWNERS
.github/workflows/ @platform-team
```

---

## 11. Other CI/CD Tools Comparison

| Feature | GitHub Actions | GitLab CI | Jenkins | CircleCI | Azure DevOps |
|---------|---------------|-----------|---------|----------|--------------|
| Config | YAML | YAML | Groovy/YAML | YAML | YAML |
| Hosting | SaaS + self-hosted | SaaS + self-managed | Self-hosted | SaaS | SaaS + self-hosted |
| Marketplace | 15,000+ actions | Templates | 1800+ plugins | Orbs | Extensions |
| Free tier | 2000 min/mo | 400 min/mo | Free (self) | 6000 credits | 1800 min/mo |
| Docker support | Native | Native | Plugin | Native | Native |
| Secrets | Encrypted | Masked vars | Credentials | Contexts | Variable groups |
| Matrix builds | Yes | Parallel | Plugin | Yes | Yes |
| Auto-scaling | ARC (K8s) | K8s executor | K8s plugin | Built-in | VMSS agents |
| Best for | GitHub repos | GitLab repos | Complex pipelines | Speed | Azure/MS stack |

---

## 12. AWS CodePipeline & CodeBuild

### CodePipeline

Orchestration service with stages:
```
Source (GitHub/CodeCommit) → Build (CodeBuild) → Test → Deploy (CodeDeploy/ECS/S3)
```

### CodeBuild - buildspec.yml

```yaml
version: 0.2

env:
  variables:
    NODE_ENV: production
  secrets-manager:
    DB_PASSWORD: prod/db:password

phases:
  install:
    runtime-versions:
      nodejs: 20
    commands:
      - npm ci
  pre_build:
    commands:
      - echo "Logging into ECR..."
      - aws ecr get-login-password | docker login --username AWS --password-stdin $ECR_REPO
  build:
    commands:
      - npm run build
      - docker build -t $ECR_REPO:$CODEBUILD_RESOLVED_SOURCE_VERSION .
      - docker push $ECR_REPO:$CODEBUILD_RESOLVED_SOURCE_VERSION
  post_build:
    commands:
      - echo "Build completed"
      - printf '[{"name":"app","imageUri":"%s"}]' $ECR_REPO:$CODEBUILD_RESOLVED_SOURCE_VERSION > imagedefinitions.json

artifacts:
  files:
    - imagedefinitions.json
    - appspec.yml

cache:
  paths:
    - node_modules/**/*
```

### CodeDeploy Strategies
- **In-place** (EC2): stop → update → start
- **Blue/Green** (EC2/ECS): new fleet → switch traffic → terminate old
- **Canary** (Lambda): 10% → wait → 100%
- **Linear** (Lambda): 10% every 2 minutes

### GitHub Actions vs AWS CodePipeline

| Aspect | GitHub Actions | CodePipeline + CodeBuild |
|--------|---------------|--------------------------|
| Integration | GitHub native | AWS native |
| Config | YAML in repo | Console + buildspec |
| Runners | GitHub/self-hosted | Managed build environments |
| Cost | Per minute | Per build minute |
| Flexibility | Very high | AWS ecosystem focused |
| IAM | OIDC federation | Native IAM roles |

---

## 13. Scenario-Based Interview Questions

### Q1: "Design CI/CD for a microservices monorepo"

**Answer:**
- Use path filters to detect which services changed
- Build/test only affected services + dependents
- Shared libraries trigger downstream rebuilds
- Each service has its own deploy job
- Use reusable workflows for common patterns

```yaml
# Detect changes → build affected → deploy affected
jobs:
  changes:
    outputs:
      services: ${{ steps.filter.outputs.changes }}
    steps:
      - uses: dorny/paths-filter@v3
        id: filter
        with:
          filters: |
            user-service: 'services/user/**'
            order-service: 'services/order/**'

  build:
    needs: changes
    strategy:
      matrix:
        service: ${{ fromJson(needs.changes.outputs.services) }}
    steps:
      - run: docker build -t ${{ matrix.service }}:${{ github.sha }} services/${{ matrix.service }}
```

### Q2: "Reduce CI pipeline from 30 min to 5 min"

**Answer:**
1. **Caching**: dependencies, Docker layers, build outputs
2. **Parallelization**: run lint/test/build concurrently
3. **Test splitting**: matrix strategy with shards
4. **Selective builds**: only test changed code (path filters)
5. **Larger runners**: 8-16 cores for build-heavy jobs
6. **Docker layer caching**: `cache-from: type=gha`
7. **Skip unnecessary steps**: conditional steps based on changes
8. **Incremental builds**: turbo/nx for monorepos

### Q3: "Implement zero-downtime deployment for ECS"

**Answer:**
- Use ECS rolling update with `minimumHealthyPercent: 100`, `maximumPercent: 200`
- Configure ALB health checks with appropriate thresholds
- Use `wait-for-service-stability: true` in the deploy action
- Connection draining on old tasks (deregistration_delay)
- Pre-deployment health check endpoint validation

### Q4: "Self-hosted runner auto-scaling design"

**Answer:**
- **Option A**: Actions Runner Controller (ARC) on Kubernetes
  - RunnerDeployment + HorizontalRunnerAutoscaler
  - Scale on webhook (workflow_job queued event)
  - Min 1, max N based on queue depth
- **Option B**: VM-based with webhook
  - GitHub webhook → Lambda → ASG desired count
  - Scale down on idle (no job for 10 min)
  - Use spot instances for cost savings
- Both: ephemeral flag for security

### Q5: "Secrets leaked in logs - prevention strategy"

**Answer:**
1. All secrets auto-masked by GitHub Actions (if in `secrets` context)
2. Use `::add-mask::` for dynamic secrets
3. Never use `${{ secrets.X }}` in shell interpolation directly
4. Audit third-party actions (pin to SHA)
5. Enable audit log alerts for secret access
6. Rotate all secrets if leaked
7. Use OIDC instead of long-lived credentials
8. `permissions: {}` to drop GITHUB_TOKEN when not needed

### Q6: "Design multi-environment promotion pipeline"

**Answer:**
```
PR → CI (lint/test/build) → Merge → Dev (auto) → Staging (auto + smoke tests) → Prod (manual approval)
```
- Use GitHub environments with protection rules
- Same artifact/image promoted through environments
- Environment-specific secrets (different AWS accounts)
- Smoke tests gate promotion
- Rollback: redeploy previous tag

### Q7: "Rollback strategy when production deployment fails"

**Answer:**
1. **Automated health check** after deploy (HTTP, metrics)
2. **Automatic rollback** if health check fails:
   - ECS: previous task definition
   - K8s: `kubectl rollout undo`
   - Lambda: alias shift back
3. **Manual rollback** trigger via workflow_dispatch
4. **Keep N previous artifacts** for quick rollback
5. **Database migrations** must be backward-compatible (expand/contract pattern)

### Q8: "Implement canary deployment with automated rollback"

**Answer:**
- Deploy to canary target group (5-10% traffic)
- Monitor error rate and latency for 5-10 minutes
- Compare canary metrics vs baseline
- If degradation > threshold: auto-rollback canary, alert team
- If healthy: progressive increase (25% → 50% → 100%)
- Use CloudWatch alarms + CodeDeploy or custom logic

### Q9: "Design CI/CD for infrastructure (Terraform)"

**Answer:**
- PR: `terraform plan` → post plan as PR comment
- Merge to main: `terraform apply -auto-approve`
- State in S3 with DynamoDB lock
- Separate state per environment
- Use OIDC for AWS auth
- Required review for workflow files (CODEOWNERS)
- Drift detection on schedule

### Q10: "Handle flaky tests in CI pipeline"

**Answer:**
1. **Detection**: track test pass rates over time
2. **Retry**: retry failed tests 2-3x before failing
3. **Quarantine**: move known flaky tests to separate job (non-blocking)
4. **Fix**: prioritize fixing flaky tests (they erode confidence)
5. **Reporting**: track flaky test rate as team metric
6. **Prevention**: avoid time-dependent tests, use test containers

### Q11: "Docker multi-arch builds in GitHub Actions"

**Answer:**
```yaml
- uses: docker/setup-qemu-action@v3
- uses: docker/setup-buildx-action@v3
- uses: docker/build-push-action@v5
  with:
    platforms: linux/amd64,linux/arm64
    push: true
    cache-from: type=gha
    cache-to: type=gha,mode=max
```

### Q12: "Design branch protection and merge strategy"

**Answer:**
- `main`: protected, require PR + 1 review + passing CI
- Feature branches: short-lived (<1 day ideal)
- Squash merge to main (clean history)
- Required status checks: lint, test, build, security
- Auto-delete head branches after merge
- CODEOWNERS for critical paths
- No force-push to main

### Q13: "Implement OIDC authentication for AWS deployments"

**Answer:**
1. Create IAM OIDC provider for `token.actions.githubusercontent.com`
2. Create IAM role with trust policy restricting to repo/branch
3. Use `aws-actions/configure-aws-credentials` with `role-to-assume`
4. Set `permissions: id-token: write` in workflow
5. No access keys stored anywhere

Trust policy:
```json
{
  "Condition": {
    "StringEquals": {
      "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
    },
    "StringLike": {
      "token.actions.githubusercontent.com:sub": "repo:org/repo:ref:refs/heads/main"
    }
  }
}
```

### Q14: "Cost optimization for GitHub Actions"

**Answer:**
1. Use path filters (don't run for docs changes)
2. Cancel in-progress runs (`concurrency: cancel-in-progress: true`)
3. Aggressive caching (dependencies, Docker layers)
4. Self-hosted runners for high-volume repos
5. Use `ubuntu-latest` (1x) vs macOS (10x multiplier)
6. Optimize build times (less minutes = less cost)
7. Avoid unnecessary matrix combinations
8. Use larger runners only where needed (faster = fewer minutes)

### Q15: "Design CI for mobile app (iOS + Android)"

**Answer:**
```yaml
jobs:
  android:
    runs-on: ubuntu-latest
    steps:
      - run: ./gradlew assembleRelease test
      - uses: actions/upload-artifact@v4
        with:
          name: android-apk
          path: app/build/outputs/apk/release/

  ios:
    runs-on: macos-latest  # required for Xcode
    steps:
      - run: |
          xcodebuild -scheme MyApp -sdk iphonesimulator test
          xcodebuild -scheme MyApp -sdk iphoneos archive
```
- iOS requires macOS runner (10x cost)
- Use caching for CocoaPods/Gradle
- Separate test and release builds
- Fastlane for signing and upload

### Q16: "Implement progressive delivery with feature flags"

**Answer:**
- Deploy code with features behind flags (always deployable)
- CI/CD deploys all code to prod on merge
- Feature flags control rollout: internal → beta → 10% → 100%
- Monitor metrics per flag cohort
- Instant rollback: disable flag (no redeploy)
- Tools: LaunchDarkly, Unleash, AWS AppConfig
- CI validates flag configuration (no undefined flags in code)

### Q17: "Secure a workflow against supply chain attacks"

**Answer:**
1. Pin all actions to SHA (not tags)
2. Use Dependabot for action updates with review
3. Fork critical actions to your org
4. Limit `GITHUB_TOKEN` permissions
5. Don't use `pull_request_target` with checkout of PR code
6. Verify action source (check stars, maintainers, code)
7. Use `actions/attest-build-provenance` for SLSA

### Q18: "Design CI/CD for a serverless application"

**Answer:**
```yaml
jobs:
  deploy:
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE }}
          aws-region: us-east-1
      - uses: aws-actions/setup-sam@v2
      - run: sam build
      - run: sam deploy --no-confirm-changeset --stack-name myapp-${{ inputs.env }}
```
- Use SAM/CDK/Serverless Framework
- Per-environment stacks
- Lambda versioning + aliases for canary
- API Gateway stages

### Q19: "Handle database migrations in CI/CD"

**Answer:**
- **Expand/Contract pattern**: never breaking changes
  1. Expand: add new column (nullable), deploy code that writes to both
  2. Migrate: backfill data
  3. Contract: remove old column, deploy code using only new
- Run migrations as separate step before deploy
- Test migrations against production-like data
- Rollback plan: reverse migration script
- Never drop columns in same release as code change

### Q20: "Design disaster recovery for CI/CD"

**Answer:**
- **GitHub outage**: self-hosted runners + git mirror
- **Runner failure**: auto-scaling (ARC) replaces unhealthy
- **Secrets compromise**: rotation runbook, OIDC reduces blast radius
- **Workflow corruption**: CODEOWNERS + required reviews + git history
- **Cloud region failure**: multi-region deploy pipelines
- **State corruption** (Terraform): versioned state, backup, lock
- Regular DR drills: simulate failure, measure recovery time

---

## Quick Reference: Common Workflow Patterns

### Conditional Job Execution
```yaml
jobs:
  deploy:
    if: |
      github.event_name == 'push' &&
      github.ref == 'refs/heads/main' &&
      !contains(github.event.head_commit.message, '[skip deploy]')
```

### Dynamic Matrix
```yaml
jobs:
  setup:
    outputs:
      matrix: ${{ steps.set.outputs.matrix }}
    steps:
      - id: set
        run: echo 'matrix=["svc-a","svc-b","svc-c"]' >> $GITHUB_OUTPUT
  build:
    needs: setup
    strategy:
      matrix:
        service: ${{ fromJson(needs.setup.outputs.matrix) }}
```

### Slack Notification on Failure
```yaml
- if: failure()
  uses: slackapi/slack-github-action@v1
  with:
    payload: |
      {"text": "❌ ${{ github.workflow }} failed on ${{ github.ref_name }}"}
  env:
    SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK }}
```

### Composite Action for Repeated Setup
```yaml
# .github/actions/setup/action.yml
name: 'Project Setup'
runs:
  using: 'composite'
  steps:
    - uses: actions/setup-node@v4
      with:
        node-version: '20'
        cache: 'npm'
    - run: npm ci
      shell: bash
    - run: npx prisma generate
      shell: bash
```

---

## Key Takeaways

1. **OIDC > stored secrets** for cloud authentication
2. **Pin actions to SHA** for supply chain security
3. **Cancel in-progress** + **path filters** for cost optimization
4. **Environments + protection rules** for safe production deploys
5. **Reusable workflows** for DRY CI/CD across repos
6. **Ephemeral runners** for security-sensitive workloads
7. **Matrix + caching** for fast, comprehensive testing
8. **Feature flags** decouple deploy from release
9. **Expand/contract** for safe database migrations
10. **Monitor after deploy** - CI/CD doesn't end at deployment
