# Problem 90: Data Pipeline as Code (Infrastructure)

### Problem 90: Data Pipeline as Code (Infrastructure)
```
TOOLS: Terraform (infra) + Pulumi (complex logic) + dbt (transforms)
PATTERN: GitOps - all pipeline definitions in git, CI/CD deploys
TESTING: Staging environment mirrors production (1% data sample)
PROMOTION: Dev → Staging → Production with automated quality gates
```
