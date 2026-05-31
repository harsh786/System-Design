"""
Deployment Agent

Generates deployment configurations and strategies:
- CI/CD pipeline configuration
- Deployment strategy (Blue/Green, Canary, Rolling)
- Infrastructure as Code
- Monitoring and alerting setup
"""

import json
from typing import Dict, List, Any
import structlog

from src.config.settings import Settings
from src.retrieval.vector_store import VectorStoreManager

logger = structlog.get_logger()


class DeploymentAgent:
    """
    Generates deployment configurations and orchestrates deployment strategy.
    """

    def __init__(self, vector_store: VectorStoreManager, settings: Settings):
        self.vector_store = vector_store
        self.settings = settings
        self.llm = self._init_llm()

    def _init_llm(self):
        """Initialize LLM client based on settings."""
        if self.settings.llm_provider == "openai":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=self.settings.openai_model,
                temperature=0.1,
                api_key=self.settings.openai_api_key,
            )
        elif self.settings.llm_provider == "anthropic":
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=self.settings.anthropic_model,
                temperature=0.1,
                api_key=self.settings.anthropic_api_key,
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {self.settings.llm_provider}")

    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main execution method for deployment agent.

        Args:
            state: Current agent state

        Returns:
            Updated state with deployment configurations
        """
        logger.info("deployment_agent_started")

        try:
            tech_stack = state.get("tech_stack", {})
            nfr = state.get("nfr", {})
            generated_code = state.get("generated_code", {})
            db_design = state.get("db_design_document", "")

            # Step 1: Determine deployment strategy
            deployment_strategy = self._determine_deployment_strategy(nfr)

            # Step 2: Generate CI/CD pipeline
            ci_cd_pipeline = await self._generate_ci_cd_pipeline(
                tech_stack=tech_stack,
                deployment_strategy=deployment_strategy,
                generated_code=generated_code,
            )

            # Step 3: Generate Infrastructure as Code
            iac_configs = await self._generate_iac(
                tech_stack=tech_stack,
                nfr=nfr,
                db_design=db_design,
            )

            # Step 4: Generate Kubernetes manifests (if applicable)
            k8s_manifests = await self._generate_k8s_manifests(
                tech_stack=tech_stack,
                nfr=nfr,
                deployment_strategy=deployment_strategy,
            )

            # Step 5: Generate Docker configurations
            docker_configs = await self._generate_docker_configs(
                tech_stack=tech_stack,
                generated_code=generated_code,
            )

            # Step 6: Generate monitoring setup
            monitoring_setup = await self._generate_monitoring_setup(
                tech_stack=tech_stack,
                nfr=nfr,
            )

            # Combine all deployment configs
            deployment_configs = {
                **ci_cd_pipeline,
                **iac_configs,
                **k8s_manifests,
                **docker_configs,
                **monitoring_setup,
            }

            logger.info(
                "deployment_agent_complete",
                strategy=deployment_strategy,
                configs_generated=len(deployment_configs),
            )

            return {
                "deployment_strategy": deployment_strategy,
                "ci_cd_pipeline": ci_cd_pipeline,
                "deployment_configs": deployment_configs,
                "monitoring_setup": monitoring_setup,
                "current_agent": "deployment_agent",
            }

        except Exception as e:
            logger.error("deployment_agent_failed", error=str(e))
            return {
                "error": f"Deployment configuration failed: {str(e)}",
                "current_agent": "deployment_agent",
            }

    def _determine_deployment_strategy(self, nfr: Dict) -> str:
        """
        Determine appropriate deployment strategy based on NFRs.
        """
        availability_target = nfr.get("availability", "99.9%")
        
        # Parse availability percentage
        try:
            availability = float(availability_target.replace("%", ""))
        except:
            availability = 99.0

        # High availability requires zero-downtime deployment
        if availability >= 99.9:
            return "blue_green"  # or canary
        elif availability >= 99.0:
            return "rolling"
        else:
            return "recreate"

    async def _generate_ci_cd_pipeline(
        self,
        tech_stack: Dict,
        deployment_strategy: str,
        generated_code: Dict[str, str],
    ) -> Dict[str, str]:
        """
        Generate CI/CD pipeline configuration (GitHub Actions, GitLab CI, etc.)
        """
        languages = tech_stack.get("languages", [])

        # Retrieve CI/CD examples
        examples = self.vector_store.search(
            query=f"CI/CD pipeline GitHub Actions {deployment_strategy}",
            k=2,
        )

        prompt = f"""
Generate a comprehensive CI/CD pipeline configuration for GitHub Actions.

## Technology Stack
{json.dumps(tech_stack, indent=2)}

## Deployment Strategy
{deployment_strategy}

## Reference Examples
{self._format_examples(examples)}

Generate a complete GitHub Actions workflow that includes:

1. **Test Stage**
   - Install dependencies
   - Run linters
   - Run unit tests
   - Run integration tests
   - Generate coverage report

2. **Security Stage**
   - SAST scanning (Bandit/Semgrep)
   - Dependency vulnerability scanning
   - Secret scanning

3. **Build Stage**
   - Build Docker image
   - Tag with commit SHA and version
   - Run smoke tests on image

4. **Deploy Stage** (using {deployment_strategy} strategy)
   - Deploy to staging (auto)
   - Run E2E tests
   - Deploy to production (manual approval)
   - Implement {deployment_strategy} deployment
   - Health checks and rollback on failure

5. **Post-Deploy**
   - Run smoke tests
   - Update monitoring dashboards
   - Send notifications

Output format:
```filename: .github/workflows/deploy.yml
<yaml content>
```

Also generate:
```filename: .github/workflows/pr-check.yml
<yaml content for PR checks>
```

Start generating:
"""

        try:
            response = await self.llm.ainvoke(prompt)
            pipeline_files = self._parse_code_blocks(response.content)
            return pipeline_files

        except Exception as e:
            logger.error("ci_cd_generation_failed", error=str(e))
            return {}

    async def _generate_iac(
        self,
        tech_stack: Dict,
        nfr: Dict,
        db_design: str,
    ) -> Dict[str, str]:
        """
        Generate Infrastructure as Code (Terraform, CloudFormation, Pulumi).
        """
        examples = self.vector_store.search(
            query="Terraform AWS infrastructure microservice RDS",
            k=2,
        )

        prompt = f"""
Generate Terraform configuration for deploying the application infrastructure on AWS.

## Technology Stack
{json.dumps(tech_stack, indent=2)}

## NFR Requirements
{json.dumps(nfr, indent=2)}

## Database Design (Summary)
{db_design[:500]}

## Reference Examples
{self._format_examples(examples)}

Generate Terraform modules for:

1. **Network** (VPC, subnets, security groups)
   - Public and private subnets across 3 AZs
   - NAT gateways
   - Internet gateway
   - Security groups

2. **Compute** (ECS/EKS for containers or EC2)
   - Auto-scaling configuration
   - Load balancer (ALB)
   - Target groups

3. **Database** (RDS, DynamoDB, ElastiCache)
   - Primary database with read replicas
   - Backup configuration
   - Cache layer (Redis)

4. **Storage** (S3 buckets)
   - Application assets
   - Logs
   - Backups

5. **Monitoring** (CloudWatch, SNS)
   - Log groups
   - Alarms
   - SNS topics for alerts

6. **IAM** (Roles and policies)
   - ECS task roles
   - Lambda execution roles

Output format:
```filename: terraform/main.tf
<terraform content>
```

```filename: terraform/variables.tf
<variables>
```

```filename: terraform/outputs.tf
<outputs>
```

```filename: terraform/modules/microservice/main.tf
<module content>
```

Start generating:
"""

        try:
            response = await self.llm.ainvoke(prompt)
            iac_files = self._parse_code_blocks(response.content)
            return iac_files

        except Exception as e:
            logger.error("iac_generation_failed", error=str(e))
            return {}

    async def _generate_k8s_manifests(
        self,
        tech_stack: Dict,
        nfr: Dict,
        deployment_strategy: str,
    ) -> Dict[str, str]:
        """
        Generate Kubernetes manifests.
        """
        examples = self.vector_store.search(
            query=f"Kubernetes deployment manifest {deployment_strategy} autoscaling",
            k=2,
        )

        prompt = f"""
Generate Kubernetes manifests for deploying the application.

## Technology Stack
{json.dumps(tech_stack, indent=2)}

## NFR Requirements
{json.dumps(nfr, indent=2)}

## Deployment Strategy
{deployment_strategy}

## Reference Examples
{self._format_examples(examples)}

Generate manifests for:

1. **Deployment**
   - Replicas based on NFRs
   - Resource requests/limits
   - Health checks (liveness, readiness)
   - Environment variables
   - Secrets management

2. **Service**
   - ClusterIP service for internal communication
   - Service ports

3. **Ingress**
   - External access configuration
   - TLS termination
   - Path-based routing

4. **HorizontalPodAutoscaler**
   - CPU/Memory based scaling
   - Min/max replicas

5. **ConfigMap**
   - Application configuration

6. **Secret**
   - Database credentials
   - API keys

7. **ServiceAccount & RBAC**
   - Permissions for the application

Output format:
```filename: k8s/deployment.yaml
<yaml content>
```

```filename: k8s/service.yaml
<yaml content>
```

```filename: k8s/ingress.yaml
<yaml content>
```

```filename: k8s/hpa.yaml
<yaml content>
```

Start generating:
"""

        try:
            response = await self.llm.ainvoke(prompt)
            k8s_files = self._parse_code_blocks(response.content)
            return k8s_files

        except Exception as e:
            logger.error("k8s_generation_failed", error=str(e))
            return {}

    async def _generate_docker_configs(
        self,
        tech_stack: Dict,
        generated_code: Dict[str, str],
    ) -> Dict[str, str]:
        """
        Generate Dockerfile and docker-compose.yml.
        """
        languages = tech_stack.get("languages", [])

        prompt = f"""
Generate Docker configuration files.

## Technology Stack
{json.dumps(tech_stack, indent=2)}

## Generated Code Files
{', '.join(list(generated_code.keys())[:20])}

Generate:

1. **Dockerfile** (multi-stage, optimized for production)
   - Use appropriate base image for {', '.join(languages)}
   - Multi-stage build (build stage + production stage)
   - Install dependencies
   - Copy application code
   - Non-root user for security
   - Health check
   - Proper layer caching

2. **docker-compose.yml** (for local development)
   - Application service
   - Database service
   - Cache service (Redis)
   - Volume mounts
   - Environment variables
   - Health checks

3. **.dockerignore**
   - Ignore unnecessary files

Output format:
```filename: Dockerfile
<dockerfile content>
```

```filename: docker-compose.yml
<yaml content>
```

```filename: .dockerignore
<content>
```

Start generating:
"""

        try:
            response = await self.llm.ainvoke(prompt)
            docker_files = self._parse_code_blocks(response.content)
            return docker_files

        except Exception as e:
            logger.error("docker_generation_failed", error=str(e))
            return {}

    async def _generate_monitoring_setup(
        self,
        tech_stack: Dict,
        nfr: Dict,
    ) -> Dict[str, str]:
        """
        Generate monitoring and alerting configurations.
        """
        examples = self.vector_store.search(
            query="Prometheus Grafana monitoring configuration alerts",
            k=2,
        )

        prompt = f"""
Generate monitoring and alerting configuration.

## Technology Stack
{json.dumps(tech_stack, indent=2)}

## NFR Requirements
{json.dumps(nfr, indent=2)}

## Reference Examples
{self._format_examples(examples)}

Generate:

1. **Prometheus Configuration** (prometheus.yml)
   - Scrape configs for application metrics
   - Recording rules
   - Alert rules

2. **Alert Rules** (alerts/application.yml)
   - High error rate (> 5%)
   - High latency (p95 > threshold from NFR)
   - Low availability
   - Database connection pool exhaustion
   - Memory usage > 90%
   - Disk usage > 80%

3. **Grafana Dashboard** (dashboards/application.json)
   - JSON dashboard definition
   - Panels for: request rate, error rate, latency, saturation
   - Database metrics
   - Infrastructure metrics

4. **Logging Configuration** (logging.yml, if applicable)
   - Log aggregation setup
   - Log retention policies

Output format:
```filename: monitoring/prometheus.yml
<yaml content>
```

```filename: monitoring/alerts/application-alerts.yml
<yaml content>
```

```filename: monitoring/dashboards/application-dashboard.json
<json content>
```

Start generating:
"""

        try:
            response = await self.llm.ainvoke(prompt)
            monitoring_files = self._parse_code_blocks(response.content)
            return monitoring_files

        except Exception as e:
            logger.error("monitoring_generation_failed", error=str(e))
            return {}

    def _parse_code_blocks(self, content: str) -> Dict[str, str]:
        """
        Parse code blocks from LLM response.
        """
        code_files = {}
        lines = content.split("\n")
        current_file = None
        current_code = []

        for line in lines:
            # Check for filename marker
            if line.startswith("```filename:"):
                # Save previous file if exists
                if current_file and current_code:
                    code_files[current_file] = "\n".join(current_code)
                    current_code = []

                # Extract new filename
                current_file = line.split("```filename:")[1].strip()

            elif line.startswith("```") and current_file:
                # End of current code block
                if current_code:
                    code_files[current_file] = "\n".join(current_code)
                    current_code = []
                    current_file = None

            elif current_file:
                # Accumulate code lines
                current_code.append(line)

        # Handle last file
        if current_file and current_code:
            code_files[current_file] = "\n".join(current_code)

        return code_files

    def _format_examples(self, examples: List[Dict]) -> str:
        """Format examples for prompt context."""
        formatted = []
        for i, example in enumerate(examples[:2], 1):
            formatted.append(
                f"### Example {i}\n```\n{example.get('content', '')[:600]}\n```"
            )
        return "\n\n".join(formatted)
