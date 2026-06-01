# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Workspace Overview

This is the **Plural** development workspace — a payment gateway/fintech platform consisting of ~200+ microservices, shared libraries, infrastructure configs, and AI agent tools. The workspace is organized into two top-level directories:

- `plural/` — All payment platform services, libraries, connectors, and infrastructure
- `AGENTS/` — Autonomous AI agents (PR-Review, JIRA, Alert-Manager, Security-Review, Tech-Solutioning, PRD-Creator, Smart-Resolution, Voice-Calling-Alert)

## Tech Stack Map

| Generation | Language | Framework | Build Tool | Naming Pattern |
|---|---|---|---|---|
| v21 (legacy active) | Java 11 | Spring Boot 2.7, WebFlux | Maven | `Plural_*Servicev21`, `Plural_*Service` |
| NXT (greenfield) | Kotlin 1.9/2.x, JVM 17 | Ktor 2.3 | Gradle Kotlin DSL | `nxt-*-service` |
| BFF / Auth | TypeScript | Express, Webpack, pm2 | npm | `*-bff-service`, `Plural_Repo_Merchant*` |
| Infra (setu) | Go 1.20 | net/http, GORM | go mod | `setu-*-service` |
| AI / Testing | Python 3.10–3.13 | FastAPI, LangChain, Google ADK, pytest | pip/poetry | `plural_chatbot_*`, `nxt-agentic-*`, `Plural_FunctionalTests` |
| Decision Engine | Rust 1.85 | Axum 0.7, Diesel | Cargo | `decision-engine` |
| Legacy | C#/.NET | WCF | MSBuild | `Plural_XT_Mono_*` |

## Shared Library Hierarchy

### Java v21 services
```
Plural_EdgeParentv21 (parent POM)
├── Plural_ServiceCommon_21 (shared libs: constants, security, POJOs, DAL, cache, DTOs, error handling, message listener)
├── Plural_ServiceClientV21 (service clients: merchant, transaction, bin, card-connector, acquirer, token, UPI, etc.)
├── Plural_ConnectorSchemaLibrary (JSON schemas for connector request/response)
└── Plural_CardSchema / Plural_HdfcCardSchema / Plural_AxisCardSchema (per-acquirer schemas)
```

### Kotlin NXT services
```
ktor-commons (dev.plural:ktor-commons) — shared Kotlin utilities
nxt-message-contracts (dev.plural:nxt-message-contracts) — Protobuf contracts via Buf toolchain
error-code-mapper — canonical error codes
openapi-messages — generated OpenAPI types
```

## Artifact Repositories

- **Java v21**: Nexus at `nexus.pinelabs.com/repository/plural-maven-common-hosted`
- **Kotlin NXT**: AWS CodeArtifact at `plural-artifacts-305714281830.d.codeartifact.ap-south-1.amazonaws.com/maven/plural-repo-maven/`
- **Docker images**: ECR at `305714281830.dkr.ecr.ap-south-1.amazonaws.com/app-images`
- **Helm charts**: S3 at `s3://plural-chart-server/stable`

## Common Build & Test Commands

### Java v21 services (Maven)
```bash
mvn clean install                        # build + unit tests
mvn clean install -DskipTests            # build only
mvn test                                 # unit tests
mvn test -Dtest=MyTestClass              # single test class
mvn test -Dtest=MyTestClass#methodName   # single test method
mvn verify                               # build + integration tests
mvn jacoco:report                        # coverage report
```

### Kotlin NXT services (Gradle)
```bash
./gradlew build                          # build + tests
./gradlew test                           # unit tests
./gradlew test --tests "com.example.MyTest"  # single test class
./gradlew koverVerify                    # coverage enforcement
./gradlew koverHtmlReport                # coverage HTML report
```

### Node.js services
```bash
npm install                              # install deps
npm run build                            # webpack build
npm test                                 # jest tests
npm run test -- --testPathPattern=myTest  # single test
npm start                                # pm2 start
```

### Go services (setu)
```bash
make build                               # build binary
make test                                # run tests
make docker-build                        # docker image
docker-compose up                        # local dev with deps (Keycloak, PostgreSQL, OPA)
```

### Python functional tests
```bash
pip install -r requirements.txt
pytest tests/ --alluredir=allure-results  # run with allure reporting
pytest -m smoke                          # smoke tests only
pytest -m "api and not slow"             # filtered by markers
```

## Infrastructure Architecture

### Kubernetes (EKS)
- All services deploy via Helm, wrapping the shared `plural-apps-common` chart (from `Plural_Ops/charts/plural-apps-common`)
- Environments: `dev`, `uat`, `prod`, `prod.dr` (disaster recovery)
- Each service Helm chart lives in `<service>/helm/` or `<service>/charts/`
- Standard probe endpoints: `/health/live` (liveness) and `/health/ready` (readiness) on port 8081

### API Gateway
- **Kong** for external-facing APIs (`Plural_Repo_Kong_API_Gateway`)
- **nginx-internal** for internal service-to-service via K8s ingress

### Configuration
- **Spring Cloud Config** (`Plural_CloudConfigServer`) backed by git repo (`Plural_CloudConfigRepository`)
- Properties per service per environment in `Plural_CloudConfigRepository/`

### Messaging
- Apache Kafka on **AWS MSK** with IAM authentication
- Java: `spring-kafka`, Node.js: `KafkaJS` with `@aws-sdk/client-kafka` SASL signer
- Protobuf-based contracts for NXT services (`nxt-message-contracts`)

### Databases
- **PostgreSQL** (RDS/Aurora) — standard for new services per ADR-0002
- **MSSQL** (SQL Server) — legacy services, being migrated
- **Redis** (ElastiCache) — caching layer
- **MongoDB** — some services

### Secrets
- AWS Secrets Manager + External Secrets Operator syncing to K8s secrets

### Observability (per ADR-0003)
- **Traces**: OpenTelemetry → OTLP → Last9 (`otlp-aps1.last9.io:443`)
- **Metrics**: OpenTelemetry SDK → Prometheus → AWS AMP
- **Logs**: logstash-logback-encoder → structured JSON → Loki
- **Dashboards**: Grafana
- **APM**: NewRelic (some older Node.js services)
- Java services bundle `opentelemetry-javaagent.jar` v2.8.0 in Docker images

### IaC
- **Terraform** (HCL) in `Plural_Ops/terraform/` — EKS, RDS, MSK, ElastiCache, OpenSearch, S3, ECR, VPC, IAM
- **CDKTF** (Python) in `Plural_Infra_TF/` for NXT infra
- **Atlantis** for GitOps-style Terraform PR automation

### CI/CD
- **Jenkins** (`Plural_Jenkins-Libraries`) for service builds/deploys
- **GitHub Actions** for AGENTS repos

## Architecture Decision Records

Located in `plural/plural-architecture/ADRs/doc/adr/`:
- **ADR-0002**: PostgreSQL as default relational database (migrating from MSSQL)
- **ADR-0003**: Standardized observability — OpenTelemetry, structured logging, `/health/live` + `/health/ready`, mandatory alerting

## Key Service Relationships

The **Card Gateway Service** (`Plural_CardGatewayServicev21`) is the central orchestrator, wiring to:
- `transaction-data-service` — transaction persistence
- `merchant-service` — merchant config/auth
- `acquirer-service` — acquirer routing
- `card-connector-service` — bank connector dispatch
- `nxt-customer-vault-mgm-service` — tokenization/card vault (NXT service)
- `network-gateway-service` — card network communication

### NXT Payment Flow
- `nxt_payment_order_service` — order management, Debezium CDC for event sourcing
- `payment-option-service` — payment method selection
- `nxt-offer-service` / `nxt-offer-processing-service` — offer evaluation
- `webhook-service` — merchant notification delivery (Svix-based)

## NXT Service Template

`plural/nxt-service-template/` is the reference skeleton for creating new Kotlin NXT services. Use it as the starting point for new services.

## Testing Strategy

| Layer | Java v21 | Kotlin NXT | Node.js | E2E |
|---|---|---|---|---|
| Unit | JUnit 5, Mockito | JUnit 5, MockK | Jest, ts-jest | — |
| Integration | SpringBootTest, Testcontainers | Ktor test, embedded-kafka | supertest | — |
| Contract/Mock | WireMock | WireMock 3.5 | — | — |
| Coverage | JaCoCo | Kover (75–95% enforced) | Jest built-in | — |
| Functional/E2E | — | — | — | pytest + Allure + Playwright + Selenium |
| BDD | Cucumber (PluralQuality_Bdd) | — | — | — |

## AGENTS Directory

Eight autonomous AI agents in `AGENTS/`:
- **PR-Review-Agent**: Claude-powered code review daemon, polls GitHub, posts review comments
- **JIRA-Agent**: Automated JIRA ticket management
- **Alert-Manager-Agent**: Incident alerting automation
- **Security-Review-Agent**: Security scanning
- **Tech-Solutioning-Agent**: Technical architecture recommendations (has its own `CLAUDE.md` with Plural context)
- **PRD-Creator-Agent**: Product requirement document generation
- **Smart-Resolution-Agent**: Incident resolution
- **Voice-Calling-Alert-Agent**: Voice-based alerting

All agents use Python with the Anthropic Claude SDK.
