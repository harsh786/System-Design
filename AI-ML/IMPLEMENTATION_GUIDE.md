# Implementation Guide: Extended Autonomous SDLC Agent

This guide walks you through implementing and using the extended autonomous agent that handles the complete software development lifecycle from PRD analysis to deployment.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Usage Modes](#usage-modes)
5. [Agent Customization](#agent-customization)
6. [Integration with GitHub Copilot](#integration-with-github-copilot)
7. [Troubleshooting](#troubleshooting)
8. [Best Practices](#best-practices)

---

## Prerequisites

### Required Tools

- **Python 3.11+**
- **Git**
- **Docker** (for deployment configuration generation)
- **OpenAI API Key** or **Anthropic API Key**

### Optional Tools (for full functionality)

- **Bandit** - Python security scanner: `pip install bandit`
- **Semgrep** - Multi-language SAST: `pip install semgrep`
- **Safety** - Python dependency scanner: `pip install safety`
- **Tree-sitter** - Code parsing (installed via pip)

### System Requirements

- **Memory**: 8GB RAM minimum, 16GB recommended
- **Storage**: 10GB free space
- **Network**: Stable internet for LLM API calls

---

## Installation

### Step 1: Clone the Repository

```bash
cd /Users/harsh.kumar01/Documents/learning/learning-conv/System-Design/AI-ML/system-design-agent
```

### Step 2: Install Dependencies

```bash
# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install the package with all dependencies
pip install -e ".[dev]"
```

### Step 3: Install Optional Security Tools

```bash
# Python security tools
pip install bandit safety

# Semgrep (multi-language)
pip install semgrep
```

### Step 4: Verify Installation

```bash
python -c "import src; print('Installation successful!')"
```

---

## Configuration

### Step 1: Environment Variables

Create a `.env` file in the project root:

```bash
# .env

# ─── LLM Configuration ───
LLM_PROVIDER=anthropic  # or openai
ANTHROPIC_API_KEY=your_anthropic_api_key_here
OPENAI_API_KEY=your_openai_api_key_here

# ─── Model Selection ───
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
OPENAI_MODEL=gpt-4o

# ─── Confluence (Optional) ───
CONFLUENCE_URL=https://your-org.atlassian.net
CONFLUENCE_TOKEN=your_confluence_api_token
CONFLUENCE_USER_EMAIL=your-email@company.com

# ─── Vector Store ───
VECTOR_STORE=chromadb  # or pinecone, weaviate
CHROMADB_PATH=./vector_store

# ─── Agent Settings ───
REVIEW_MAX_ITERATIONS=3
SECURITY_AUTO_FIX=true
PR_AUTO_APPROVE_THRESHOLD=9.0

# ─── Output ───
DEFAULT_OUTPUT_DIR=./output
```

### Step 2: Configuration File

Edit `src/config/settings.py` or create `config/agent_config.yaml`:

```yaml
# config/agent_config.yaml

agent:
  model: "claude-3-5-sonnet-20241022"
  temperature: 0.1
  max_tokens: 4096

phases:
  analysis:
    enabled: true
  design:
    enabled: true
  implementation:
    enabled: true
    languages: [python, typescript, go]
    frameworks:
      python: fastapi
      typescript: nestjs
      go: gin
  security_review:
    enabled: true
    auto_fix: true
    tools: [bandit, semgrep, safety]
  pr_review:
    enabled: true
    auto_approve_threshold: 9.0
  deployment:
    enabled: true
    strategy: canary  # blue_green, canary, rolling, recreate

code_generation:
  style: pep8
  include_docstrings: true
  include_type_hints: true
  include_logging: true
  include_opentelemetry: true

security:
  compliance: [OWASP_TOP_10, GDPR]
  severity_threshold: HIGH
```

---

## Usage Modes

### Mode 1: Full Pipeline (PRD → Deployment)

Generate everything from PRD to deployment configs:

```bash
python -m src.main \
  --mode full \
  --prd-file "./sample-prd.md" \
  --repo-path "../" \
  --output-dir "./output/order-tracking-v2" \
  --enable-all-phases
```

**Output Structure:**
```
output/order-tracking-v2/
├── design/
│   ├── HLD.md
│   ├── DB_DESIGN.md
│   └── LLD/
│       ├── OrderService.md
│       ├── PaymentService.md
│       └── NotificationService.md
├── code/
│   ├── src/
│   │   ├── services/
│   │   │   ├── order_service.py
│   │   │   └── payment_service.py
│   │   ├── models/
│   │   ├── repositories/
│   │   └── config/
│   └── tests/
│       ├── unit/
│       └── integration/
├── infrastructure/
│   ├── terraform/
│   ├── k8s/
│   ├── Dockerfile
│   └── docker-compose.yml
├── ci-cd/
│   ├── .github/workflows/deploy.yml
│   └── .github/workflows/pr-check.yml
├── monitoring/
│   ├── prometheus.yml
│   └── grafana-dashboards/
└── reports/
    ├── SECURITY_REVIEW.md
    ├── PR_REVIEW.md
    └── DEPLOYMENT_GUIDE.md
```

### Mode 2: Design Only (No Code Generation)

Useful for architecture review:

```bash
python -m src.main \
  --mode design \
  --prd-file "./sample-prd.md" \
  --context-dir "../" \
  --output-dir "./designs/payment-gateway" \
  --phases analysis,design
```

### Mode 3: Implementation from Existing Design

Generate code from pre-approved designs:

```bash
python -m src.main \
  --mode implement \
  --design-dir "./designs/payment-gateway" \
  --output-dir "./code/payment-gateway" \
  --phases implementation,security_review,pr_review
```

### Mode 4: Security Review Only

Audit existing code:

```bash
python -m src.main \
  --mode security-review \
  --code-path "./existing-service/src" \
  --output-dir "./security-reports"
```

### Mode 5: Incremental (Design → Review → Implement)

Step-by-step workflow with manual approvals:

```bash
# Step 1: Generate design
python -m src.main --mode design --prd-file prd.md --output-dir output/

# [Manual review of design]

# Step 2: Generate code from approved design
python -m src.main --mode implement --design-dir output/design/ --output-dir output/

# [Review generated code]

# Step 3: Generate deployment configs
python -m src.main --mode deployment --code-path output/code/ --output-dir output/
```

---

## Agent Customization

### Adding a New Programming Language

**1. Update Code Generator Agent**

Edit `src/agents/code_generator.py`:

```python
async def _generate_rust_code(
    self,
    component_name: str,
    lld_content: str,
    db_design: str,
    security_requirements: str,
) -> Dict[str, str]:
    """Generate Rust code using Actix-web."""
    
    prompt = f"""
Generate production-ready Rust code using Actix-web.

## Component: {component_name}
## LLD: {lld_content}

Generate:
1. Main handler (main.rs)
2. Models (models.rs)
3. Handlers (handlers/)
4. Database layer (db.rs)
5. Configuration (config.rs)

Requirements:
- Use async/await
- Implement proper error handling
- Add logging with tracing
- Use strong typing
"""
    
    response = await self.llm.ainvoke(prompt)
    return self._parse_code_blocks(response.content)
```

**2. Update Code Analyzer**

Add Rust detection in `src/agents/code_analyzer.py`:

```python
# In _identify_tech_stack method
if any("Cargo.toml" in f for f in key_files):
    tech_stack["languages"].append("Rust")
    tech_stack["dependencies"]["rust"] = self._parse_cargo_deps(repo_path)
```

### Adding a New Security Tool

**1. Implement Scanner in Security Review Agent**

Edit `src/agents/security_review_agent.py`:

```python
def _run_gosec(self, code_dir: str) -> Dict[str, List[Dict]]:
    """Run Gosec security scanner for Go."""
    results = {"critical": [], "high": [], "medium": [], "low": []}
    
    try:
        result = subprocess.run(
            ["gosec", "-fmt=json", "./..."],
            cwd=code_dir,
            capture_output=True,
            text=True,
        )
        
        if result.stdout:
            gosec_output = json.loads(result.stdout)
            for issue in gosec_output.get("Issues", []):
                severity_map = {
                    "HIGH": "high",
                    "MEDIUM": "medium",
                    "LOW": "low",
                }
                severity = severity_map.get(issue.get("severity"), "low")
                
                results[severity].append({
                    "tool": "gosec",
                    "file": issue.get("file"),
                    "line": issue.get("line"),
                    "issue": issue.get("details"),
                    "rule_id": issue.get("rule_id"),
                })
    
    except Exception as e:
        logger.warning("gosec_failed", error=str(e))
    
    return results
```

**2. Add to SAST Analysis**

```python
# In _run_sast_analysis method
if "Go" in languages:
    gosec_results = self._run_gosec(code_dir)
    self._merge_sast_results(sast_results, gosec_results)
```

### Customizing Deployment Strategy

**1. Add Custom Strategy**

Edit `src/agents/deployment_agent.py`:

```python
async def _generate_progressive_delivery_pipeline(
    self,
    tech_stack: Dict,
) -> Dict[str, str]:
    """Generate progressive delivery with feature flags."""
    
    prompt = f"""
Generate a progressive delivery pipeline using Flagger and Istio.

## Requirements
- Automated canary analysis
- Feature flag integration (LaunchDarkly)
- Gradual traffic shifting (10% → 25% → 50% → 100%)
- Automatic rollback on metric degradation

## Technology Stack
{json.dumps(tech_stack, indent=2)}

Generate Kubernetes manifests for Flagger, Istio, and the application.
"""
    
    response = await self.llm.ainvoke(prompt)
    return self._parse_code_blocks(response.content)
```

### Adding Compliance Frameworks

Edit `src/agents/security_review_agent.py`:

```python
async def _check_hipaa_compliance(
    self,
    generated_code: Dict[str, str],
) -> Dict[str, Any]:
    """Check HIPAA compliance for healthcare applications."""
    
    prompt = f"""
Evaluate HIPAA compliance for this codebase.

## Key HIPAA Requirements
1. Data encryption (at rest and in transit)
2. Access controls and audit logs
3. PHI data handling
4. Breach notification mechanisms

## Code Summary
{self._summarize_code(generated_code)}

Output compliance status for each requirement.
"""
    
    response = await self.llm.ainvoke(prompt)
    # Parse and return compliance results
```

---

## Integration with GitHub Copilot

### Setup MCP Server

**1. Create MCP Configuration**

Create `mcp_config.json`:

```json
{
  "mcpServers": {
    "autonomous-sdlc-agent": {
      "command": "python",
      "args": ["-m", "src.mcp_server.server"],
      "cwd": "/Users/harsh.kumar01/Documents/learning/learning-conv/System-Design/AI-ML/system-design-agent",
      "env": {
        "ANTHROPIC_API_KEY": "your-key",
        "LLM_PROVIDER": "anthropic",
        "DEFAULT_OUTPUT_DIR": "./output"
      }
    }
  }
}
```

**2. Add to VS Code Settings**

Add to `.vscode/settings.json` or user settings:

```json
{
  "mcp.servers": {
    "autonomous-sdlc-agent": {
      "command": "python",
      "args": ["-m", "src.mcp_server.server"],
      "cwd": "/Users/harsh.kumar01/Documents/learning/learning-conv/System-Design/AI-ML/system-design-agent",
      "env": {
        "ANTHROPIC_API_KEY": "${env:ANTHROPIC_API_KEY}"
      }
    }
  }
}
```

**3. Use in Copilot Chat**

```
@autonomous-sdlc-agent full-pipeline --prd docs/payment-feature.md

@autonomous-sdlc-agent design-only --prd confluence:ENG/12345

@autonomous-sdlc-agent implement --design output/payment/design/

@autonomous-sdlc-agent review-security --code src/payment-service/
```

### MCP Tools Available

- `generate_full_sdlc` - Complete pipeline
- `generate_design` - Design phase only
- `generate_code` - Implementation phase
- `security_review` - Security audit
- `pr_review` - Code review
- `deployment_config` - Generate deployment configs

---

## Troubleshooting

### Issue: LLM API Rate Limits

**Solution**: Add retry logic and exponential backoff

Edit `src/config/settings.py`:

```python
from tenacity import retry, wait_exponential, stop_after_attempt

@retry(
    wait=wait_exponential(multiplier=1, min=4, max=60),
    stop=stop_after_attempt(5)
)
async def call_llm_with_retry(llm, prompt):
    return await llm.ainvoke(prompt)
```

### Issue: Vector Store Errors

**Problem**: ChromaDB persistence errors

**Solution**: Clear and rebuild vector store

```bash
rm -rf ./vector_store
python -m src.ingestion.build_vector_store --context-dir ../
```

### Issue: Security Tools Not Found

**Problem**: Bandit/Semgrep not installed

**Solution**: Install in virtual environment

```bash
source venv/bin/activate
pip install bandit semgrep safety
```

### Issue: Memory Exhaustion

**Problem**: Large codebase causes OOM

**Solution**: Process in batches

```python
# In code_analyzer.py
sample_files = self._get_sample_files(repo_path, languages)[:20]  # Limit files
```

### Issue: Generated Code Syntax Errors

**Problem**: LLM generates invalid code

**Solution**: Add syntax validation

```python
import ast

def validate_python_syntax(code: str) -> bool:
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False
```

---

## Best Practices

### 1. Incremental Development

- Start with design-only mode
- Review and approve designs manually
- Then enable code generation
- Test security review on small codebases first

### 2. Human-in-the-Loop

Always have human review for:

- Architecture deviations from existing patterns
- Critical security issues
- Production deployments
- Compliance-sensitive code (healthcare, finance)

### 3. Cost Management

```python
# Track LLM API costs
import tiktoken

def estimate_cost(prompt: str, model: str = "gpt-4o"):
    encoder = tiktoken.encoding_for_model(model)
    tokens = len(encoder.encode(prompt))
    
    # GPT-4o pricing (example)
    cost_per_1k_tokens = 0.03
    return (tokens / 1000) * cost_per_1k_tokens
```

### 4. Version Control

Commit agent-generated artifacts:

```bash
git checkout -b feature/payment-gateway-agent-generated
git add output/payment-gateway/
git commit -m "chore: Add agent-generated payment gateway implementation"
git push origin feature/payment-gateway-agent-generated
```

### 5. Testing Strategy

```bash
# Test design generation first
python -m src.main --mode design --prd sample-prd.md --output-dir test-output/

# Verify design quality manually

# Then test code generation on approved design
python -m src.main --mode implement --design-dir test-output/design/
```

### 6. Monitoring Agent Performance

```python
# Add metrics tracking
import time

start_time = time.time()
result = await agent.run(state)
duration = time.time() - start_time

logger.info(
    "agent_performance",
    agent=agent.__class__.__name__,
    duration_seconds=duration,
    tokens_used=result.get("tokens_used"),
    cost=result.get("estimated_cost"),
)
```

### 7. Prompt Engineering

For better results, customize prompts in `src/config/prompts.py`:

```python
HLD_GENERATION_PROMPT = """
You are a senior software architect with 15+ years of experience.
Generate a High-Level Design that follows these principles:
- SOLID principles
- Cloud-native patterns
- 12-factor app methodology
- Security by design

[Rest of prompt...]
"""
```

---

## Next Steps

1. **Read**: [EXTENDED_AUTONOMOUS_AGENT.md](./EXTENDED_AUTONOMOUS_AGENT.md) for architecture details
2. **Explore**: Example outputs in `output/order-tracking/`
3. **Customize**: Add your tech stack and coding standards
4. **Integrate**: Set up MCP server with GitHub Copilot
5. **Iterate**: Start with small features, scale up gradually

---

## Support & Contribution

- **Issues**: Report bugs or request features in GitHub Issues
- **Documentation**: Update this guide as you customize
- **Sharing**: Share your agent configurations and prompt improvements

---

## License

[Your License Here]
