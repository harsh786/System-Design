# AWS Architecture Concepts Roadmap for Architects

This file is a high-level AWS architecture roadmap for system design, cloud architecture, platform architecture, and architect interviews. It is not a certification dump. Focus on how each AWS service changes scalability, reliability, security, cost, and operations.

## Architect-Level Outcome

You should be able to design AWS architectures across edge, networking, compute, containers, data, messaging, security, observability, deployment, disaster recovery, and cost governance.

## AWS Interview Answer Formula

```text
Requirements -> Regions/AZs -> Network boundary -> Edge/DNS -> Compute model -> Data stores -> Async/event flow -> Security/IAM/KMS -> Observability -> Deployment -> DR -> Cost -> Trade-offs
```

## AWS Mental Model

| Layer | AWS Concepts |
| --- | --- |
| Global edge | Route 53, CloudFront, Global Accelerator, WAF, Shield, ACM. |
| Network | VPC, subnets, route tables, IGW, NAT Gateway, Security Groups, NACLs, VPC endpoints, PrivateLink, Transit Gateway, Direct Connect, VPN. |
| Compute | EC2, Auto Scaling Groups, Lambda, Batch. |
| Containers | EKS, ECS, Fargate, ECR, App Mesh, Cloud Map. |
| API entry | API Gateway, ALB, NLB, AppSync, CloudFront Functions, Lambda@Edge. |
| Data | RDS, Aurora, DynamoDB, ElastiCache, OpenSearch, Redshift, S3, EFS, EBS, FSx. |
| Messaging | SQS, SNS, EventBridge, Kinesis, MSK, Step Functions. |
| Security | IAM, STS, IAM Identity Center, Cognito, KMS, Secrets Manager, ACM, CloudHSM, GuardDuty, Security Hub, Inspector, Macie. |
| Observability | CloudWatch, X-Ray, CloudTrail, AWS Config, VPC Flow Logs. |
| Deployment/IaC | CloudFormation, CDK, CodePipeline, CodeBuild, CodeDeploy, ECR, Systems Manager. |
| Governance | Organizations, Control Tower, Service Control Policies, Budgets, Cost Explorer, Trusted Advisor. |

## Edge, DNS, and Traffic Management

### Route 53

Architect concepts:

- Hosted zones.
- Public and private DNS.
- TTL and resolver caching.
- Health checks.
- Weighted routing.
- Latency-based routing.
- Geolocation/geoproximity routing.
- Failover routing.
- Multivalue answers.
- DNS query logging.

Design rules:

- Use Route 53 for domain routing and health-aware failover.
- Use weighted routing for migration and traffic shifting.
- Use latency/geolocation routing for global user bases.
- Keep TTL low during migrations, but remember DNS failover is not instant because resolvers cache records.
- Route to CloudFront, ALB/NLB, API Gateway, or regional endpoints depending on workload.

### CloudFront

Use for:

- Static assets.
- Media.
- Global caching.
- Origin shielding.
- TLS termination at edge.
- WAF integration.
- Signed URLs/cookies for private content.

Design concerns:

- Cache keys.
- Personalized data leakage.
- Origin protection.
- Invalidation cost.
- Compression.
- HTTP/2 and HTTP/3.
- Edge compute with CloudFront Functions or Lambda@Edge.

### Global Accelerator

Use when:

- You need static anycast IPs.
- You want traffic routed over the AWS global network to regional endpoints.
- You need fast failover to healthy endpoints.

Compare:

- Route 53 is DNS-based routing.
- Global Accelerator is network-level anycast routing.

## Load Balancers

| Load Balancer | Use For | Architect Notes |
| --- | --- | --- |
| ALB | HTTP/HTTPS/gRPC, path/host routing, web/API services. | Best default for L7 microservices ingress. |
| NLB | TCP/UDP/TLS, very high throughput, static IP support. | Good for non-HTTP, pass-through, low-latency workloads. |
| GWLB | Network appliances such as firewalls/inspection. | Useful for centralized traffic inspection. |
| Classic ELB | Legacy. | Know it exists, avoid for new designs unless legacy constraint. |

Design rules:

- Use ALB for HTTP routing to ECS/EKS/EC2 services.
- Use NLB for TCP, UDP, TLS pass-through, or static IP requirements.
- Enable health checks and connection draining.
- Align idle timeouts across clients, load balancer, gateway, and services.
- Use target groups for blue-green/canary traffic shifting.

## Networking: VPC Design

### Core Components

- VPC CIDR.
- Public subnets.
- Private application subnets.
- Private database subnets.
- Route tables.
- Internet Gateway.
- NAT Gateway.
- Security Groups.
- NACLs.
- VPC endpoints.
- Private hosted zones.

### Recommended Baseline

```text
Region
  AZ-A: public subnet, private app subnet, private data subnet
  AZ-B: public subnet, private app subnet, private data subnet
  AZ-C: public subnet, private app subnet, private data subnet
```

Design rules:

- Put internet-facing load balancers in public subnets.
- Put services and databases in private subnets.
- Use NAT Gateway for outbound internet from private subnets when required.
- Prefer VPC endpoints and PrivateLink for AWS service access without public internet.
- Use Security Groups as the primary stateful firewall.
- Use NACLs carefully as stateless subnet-level controls.
- Avoid overlapping CIDRs if VPC peering, Transit Gateway, or hybrid connectivity is likely.

### Hybrid and Multi-VPC

Know:

- VPC Peering.
- Transit Gateway.
- PrivateLink.
- Site-to-Site VPN.
- Direct Connect.
- Route 53 Resolver inbound/outbound endpoints.

Interview focus:

- Hub-and-spoke networking.
- Shared services VPC.
- Private service exposure.
- On-prem connectivity.
- DNS resolution across VPC/on-prem.

## Compute Choices

| Compute | Best For | Trade-Off |
| --- | --- | --- |
| EC2 | Full control, custom runtime, stateful/legacy workloads. | You manage patching, scaling, AMIs, capacity. |
| Auto Scaling Group | EC2 fleet scaling. | Requires launch templates and health/scaling design. |
| ECS on EC2 | Containers with EC2 control. | Manage instances/capacity. |
| ECS on Fargate | Simple container serverless runtime. | Less host control; pricing model differs. |
| EKS on EC2 | Kubernetes ecosystem and portability. | Operational complexity. |
| EKS on Fargate | Kubernetes pods without node management. | Limitations and cost trade-offs. |
| Lambda | Event-driven short-lived compute. | Cold starts, timeouts, package/runtime limits, concurrency. |
| Batch | Batch jobs and queues. | Fit for async compute, not low-latency APIs. |

## EC2 Instance and Worker Node Types

### Instance Families

| Family | Use Case |
| --- | --- |
| T | Burstable small workloads, dev/test, low steady CPU. |
| M | General-purpose balanced workloads. |
| C | Compute-optimized services, CPU-heavy APIs. |
| R | Memory-optimized services, caches, in-memory workloads. |
| X / High Memory | Very large memory workloads. |
| I / D | Storage-optimized local NVMe/HDD workloads. |
| G / P | GPU workloads, ML inference/training, graphics. |
| Inf / Trn | AWS accelerator families for inference/training. |
| Graviton ARM | Cost/performance optimization where workload supports ARM. |

### Node Capacity Types

- On-Demand: predictable baseline.
- Reserved Instances/Savings Plans: steady-state cost optimization.
- Spot: fault-tolerant, interruptible workloads.
- Dedicated Hosts/Instances: compliance/licensing constraints.

### EKS Worker Node Types

| Node Type | Use When | Trade-Off |
| --- | --- | --- |
| Managed node group | Standard EKS EC2 nodes with AWS-managed lifecycle. | Good default. |
| Self-managed node group | Need custom lifecycle or unsupported configuration. | More operational burden. |
| Fargate profile | Pod-level serverless compute. | Less daemonset/host control. |
| Karpenter-provisioned nodes | Dynamic right-sized node provisioning. | Requires strong scheduling/capacity understanding. |
| Bottlerocket nodes | Container-optimized OS. | Different operational model. |
| GPU nodes | ML/video/compute acceleration. | Expensive, capacity planning critical. |
| Spot nodes | Stateless/fault-tolerant workloads. | Handle interruption and rebalance. |

Node sizing rules:

- Use many medium nodes for failure distribution and bin packing.
- Use larger nodes for high-memory/high-throughput workloads when pod density is safe.
- Keep system and daemonset overhead in capacity calculations.
- Use requests/limits based on measured workload.
- Separate critical workloads with taints, tolerations, node selectors, or dedicated node groups.
- Use topology spread constraints across AZs.

## ECS, EKS, and Fargate

### ECS

Best for:

- AWS-native container orchestration.
- Simpler operational model than Kubernetes.
- Tight IAM, CloudWatch, and ALB integration.

Concepts:

- Cluster.
- Task definition.
- Service.
- Task.
- Capacity provider.
- ECS on EC2.
- ECS on Fargate.
- Service discovery.
- Blue/green with CodeDeploy.

### EKS

Best for:

- Kubernetes ecosystem.
- Multi-cloud/platform portability.
- Operators, CRDs, service mesh, advanced scheduling.

Concepts:

- Control plane.
- Managed node groups.
- Pods, deployments, services, ingress.
- IRSA / pod identity.
- Cluster autoscaler / Karpenter.
- EKS add-ons.
- CNI and IP exhaustion.
- Network policies.
- Ingress controller / AWS Load Balancer Controller.

### Fargate

Best for:

- Serverless containers.
- Teams that do not want to manage nodes.
- Spiky or isolated workloads.

Trade-offs:

- Less host-level control.
- Per-task/pod pricing.
- Some daemonset, privileged container, and runtime limitations.
- Cold start and runtime limits to consider.

Decision rule:

```text
Choose ECS/Fargate for AWS-native simplicity, EKS for Kubernetes ecosystem and platform flexibility, EC2/ASG for maximum host control.
```

## API and Application Entry

### API Gateway

Use for:

- REST APIs.
- HTTP APIs.
- WebSocket APIs.
- Throttling.
- Request validation.
- Authorizers.
- Usage plans.
- API keys.
- Lambda/service integration.

Compare:

- API Gateway is stronger for managed API front-door features.
- ALB is often simpler and cheaper for service ingress and HTTP routing.

### AppSync

Use for:

- Managed GraphQL.
- Mobile/web data aggregation.
- Real-time subscriptions.
- Offline/mobile-friendly patterns with Amplify ecosystem.

## Identity, IAM, and Federation

### IAM

Must know:

- Users, groups, roles, policies.
- Identity-based policies.
- Resource-based policies.
- Permission boundaries.
- Service-linked roles.
- Cross-account roles.
- STS temporary credentials.
- Least privilege.
- Policy conditions.

Architect focus:

- Prefer roles over long-lived access keys.
- Use temporary credentials.
- Use least privilege with scoped resources and conditions.
- Separate human and workload identities.
- Use cross-account role assumption for multi-account access.

### Federated Identity

Know:

- IAM Identity Center.
- SAML federation.
- OIDC federation.
- Cognito user pools and identity pools.
- STS assume-role concepts.
- EKS service account federation with IAM roles for service accounts or pod identity.

Use cases:

- Enterprise SSO.
- Workforce access.
- Customer identity.
- CI/CD workload identity.
- Kubernetes pod identity.
- Cross-account access.

## KMS, Secrets, and Certificates

### KMS

Concepts:

- Customer managed keys.
- AWS managed keys.
- Envelope encryption.
- Key policies.
- Grants.
- Rotation.
- Multi-region keys.
- CloudTrail audit.

Use for:

- S3 encryption.
- RDS encryption.
- EBS encryption.
- Secrets Manager encryption.
- Application envelope encryption.

### Secrets Manager and Parameter Store

Use Secrets Manager for:

- Database credentials.
- Rotation.
- Sensitive app secrets.

Use Systems Manager Parameter Store for:

- Configuration.
- Some secure parameters.
- Lower-cost simple parameter needs.

### ACM

Use for:

- TLS certificates for ALB, CloudFront, and API Gateway.
- Managed renewal for public certificates.

## Databases and Caches

### RDS

Engines:

- PostgreSQL.
- MySQL.
- MariaDB.
- SQL Server.
- Oracle.

Architect concepts:

- Multi-AZ.
- Read replicas.
- Backups and point-in-time recovery.
- Storage autoscaling.
- Parameter groups.
- Subnet groups.
- Security groups.
- Performance Insights.
- RDS Proxy for connection pooling.

### Aurora

Concepts:

- Shared distributed storage.
- Aurora Replicas.
- Reader endpoint.
- Writer endpoint.
- Global Database.
- Serverless v2.
- Backtrack where supported.

Interview focus:

- RDS vs Aurora.
- Read scaling.
- Connection pooling.
- Failover behavior.
- Global read latency.

### DynamoDB

Concepts:

- Partition key and sort key.
- GSIs and LSIs.
- On-demand vs provisioned capacity.
- Adaptive capacity.
- Conditional writes.
- TTL.
- Streams.
- Global tables.
- Transactions.

Interview focus:

- Access-pattern-first design.
- Hot partition mitigation.
- Single-table design.
- Eventually consistent vs strongly consistent reads.

### ElastiCache

Engines:

- Redis/Valkey-style engine.
- Memcached.

Use for:

- Cache-aside.
- Session storage.
- Rate limiting.
- Distributed counters.
- Leaderboards.
- Pub/sub or streams where appropriate.

Design concerns:

- Cluster mode.
- Sharding.
- Replicas.
- Failover.
- Eviction policy.
- Hot keys.
- TTL.
- Cache stampede.

### OpenSearch

Use for:

- Full-text search.
- Logs/search analytics.
- Vector/hybrid search where appropriate.

Design concerns:

- Index lifecycle.
- Shard sizing.
- Replicas.
- Refresh interval.
- Hot/warm/cold tiers.
- Query cost.

## Storage

### S3

Use for:

- Object storage.
- Static assets.
- Data lake.
- Backups.
- Logs.

Concepts:

- Buckets and prefixes.
- Versioning.
- Lifecycle policies.
- Storage classes.
- Replication.
- Multipart upload.
- Event notifications.
- Object Lock.
- Bucket policies.
- Encryption.

### EBS

Use for:

- EC2 block storage.
- Databases on EC2.

Concepts:

- gp3/io2/st1/sc1 style trade-offs.
- IOPS and throughput.
- Snapshots.
- Encryption.

### EFS and FSx

Use for:

- Shared file systems.
- Lift-and-shift workloads.
- HPC, Windows, Lustre, NetApp, and enterprise file use cases depending on FSx type.

## Messaging and Event-Driven AWS

### SQS

Use for:

- Work queues.
- Decoupling services.
- Back-pressure.
- Retry and DLQ.

Concepts:

- Standard queues.
- FIFO queues.
- Visibility timeout.
- DLQ.
- Long polling.
- Message retention.

### SNS

Use for:

- Pub/sub fanout.
- Notifications.
- Push to SQS, Lambda, HTTP endpoints, email, or SMS where appropriate.

### EventBridge

Use for:

- Event bus.
- SaaS/AWS service integration.
- Event routing.
- Scheduled events.

Concepts:

- Event bus.
- Rules.
- Targets.
- Schema registry.
- Archive/replay.

### Kinesis and MSK

Kinesis:

- Managed streaming.
- Shards.
- Partition keys.
- Enhanced fan-out.

MSK:

- Managed Kafka.
- Topics, partitions, brokers.
- Kafka ecosystem compatibility.

### Step Functions

Use for:

- Workflow orchestration.
- Sagas.
- Long-running processes.
- Human approval where integrated.
- Retry/catch state handling.

## Analytics and Data Platform

Know:

- Glue: catalog and ETL.
- Athena: serverless SQL over S3.
- EMR: managed big data clusters.
- Redshift: data warehouse.
- Lake Formation: lake permissions/governance.
- Kinesis Data Firehose: streaming delivery.
- QuickSight: BI dashboards.
- SageMaker: ML platform.
- Bedrock: managed foundation models and GenAI app building.

Architect focus:

- OLTP systems should not serve BI directly.
- Land events/logs in S3 for replay and lakehouse.
- Use Glue, Lake Formation, and catalogs for governance.
- Choose Athena, Trino, Redshift, Snowflake, or Databricks based on workload and platform strategy.

## Observability, Audit, and Governance

### CloudWatch

- Metrics.
- Logs.
- Alarms.
- Dashboards.
- Container insights.
- Lambda insights.
- Recommended service alarms.

### X-Ray

- Distributed tracing.
- Service maps.
- Latency breakdown.

### CloudTrail

- API audit logging.
- Security investigation.
- Compliance evidence.

### AWS Config

- Resource configuration tracking.
- Compliance rules.
- Drift and change history.

### Security Services

- GuardDuty: threat detection.
- Security Hub: security findings aggregation.
- Inspector: vulnerability scanning.
- Macie: sensitive data discovery.
- Detective: investigation.
- Network Firewall: network protection.

## Deployment and IaC

Know:

- CloudFormation.
- CDK.
- SAM for serverless.
- Terraform/OpenTofu where company standard uses it.
- CodePipeline.
- CodeBuild.
- CodeDeploy.
- ECR.
- Systems Manager.
- Parameter Store.

Deployment strategies:

- Rolling.
- Blue-green.
- Canary.
- Linear rollout.
- Feature flags with AppConfig.
- ECS blue/green through CodeDeploy.
- Lambda weighted aliases.
- ALB target group shifting.

## Multi-Account and Landing Zone

Architects must know account strategy.

Concepts:

- AWS Organizations.
- Organizational Units.
- Service Control Policies.
- Control Tower.
- Landing zone.
- Shared services account.
- Security/audit/log archive account.
- Network account.
- Workload accounts by environment/team.

Why it matters:

- Blast-radius control.
- Billing separation.
- Security boundaries.
- Compliance evidence.
- Environment isolation.

## High-Level AWS Architecture Patterns

### Pattern 1: Public Web/API Platform

```text
Route 53 -> CloudFront/WAF -> ALB/API Gateway -> ECS/EKS services
                                      -> RDS/Aurora
                                      -> ElastiCache
                                      -> SQS/EventBridge
                                      -> S3
```

Use for:

- SaaS applications.
- E-commerce.
- Public APIs.

### Pattern 2: Event-Driven Serverless

```text
API Gateway -> Lambda -> DynamoDB
                    -> EventBridge/SNS/SQS
                    -> Step Functions
                    -> S3
```

Use for:

- Spiky workloads.
- Event-driven workflows.
- Small teams wanting low infrastructure management.

### Pattern 3: Kubernetes Platform

```text
Route 53 -> CloudFront/WAF -> ALB/NLB -> EKS Ingress -> Services/Pods
                                                -> RDS/Aurora/DynamoDB
                                                -> ElastiCache
                                                -> MSK/SQS/EventBridge
```

Use for:

- Platform teams.
- Kubernetes operators/CRDs.
- Multi-service product platforms.

### Pattern 4: Data Lakehouse

```text
Sources -> DMS/Kafka/Kinesis/Firehose -> S3 raw/bronze/silver/gold
                                      -> Glue Catalog/Lake Formation
                                      -> Spark/EMR/Glue/dbt
                                      -> Athena/Redshift/QuickSight
```

Use for:

- Analytics.
- Governance.
- ML features.
- BI and reporting.

## AWS Interview Trade-Offs

| Decision | Compare |
| --- | --- |
| ECS vs EKS | Simplicity vs Kubernetes ecosystem/control. |
| EC2 vs Fargate | Host control/cost tuning vs serverless container operations. |
| ALB vs API Gateway | Service ingress vs managed API product features. |
| RDS vs DynamoDB | Relational consistency/querying vs access-pattern scale. |
| Aurora vs RDS | Distributed storage/read scaling vs cost/engine compatibility. |
| SQS vs Kinesis/MSK | Work queue vs ordered stream/log. |
| SNS vs EventBridge | Simple pub/sub fanout vs event routing/integration. |
| Lambda vs containers | Event-driven serverless vs long-running service control. |
| NAT Gateway vs VPC endpoints | Simple outbound internet vs private AWS service access/cost control. |
| CloudFront vs Global Accelerator | HTTP cache/edge vs network-level anycast acceleration. |

## AWS Cost and Reliability Checklist

- Multi-AZ for critical workloads.
- Autoscaling policies.
- Reserved capacity/Savings Plans for steady workloads.
- Spot only for interruptible workloads.
- S3 lifecycle policies.
- CloudWatch log retention.
- NAT Gateway data processing cost.
- Cross-AZ and cross-region data transfer.
- RDS instance class and storage autoscaling.
- DynamoDB on-demand vs provisioned.
- ElastiCache right sizing.
- Load balancer LCU/NLCU cost.
- EKS cluster and node cost.
- KMS request cost at high volume.

## AWS Security Checklist

- Least-privilege IAM roles.
- No long-lived access keys for workloads.
- MFA and SSO for humans.
- Separate accounts/environments.
- KMS encryption for sensitive data.
- Secrets Manager rotation.
- VPC private subnets for services/databases.
- Security group least privilege.
- WAF for public apps.
- CloudTrail enabled.
- GuardDuty, Security Hub, and Config.
- S3 Block Public Access.
- ECR image scanning.
- Private endpoint strategy.

## AWS Architect Interview Questions

1. Design a SaaS platform on AWS for 10 million users.
2. When would you choose ECS/Fargate over EKS?
3. How do you design EKS worker node groups for mixed workloads?
4. ALB vs NLB vs API Gateway: when do you use each?
5. How do you design private subnets, NAT, and VPC endpoints?
6. How do you connect AWS to on-prem securely?
7. RDS vs Aurora vs DynamoDB for an order service?
8. How do you handle RDS connection pooling at high scale?
9. How do you use KMS and Secrets Manager in a production system?
10. How do you design cross-account access and federated identity?
11. SQS vs SNS vs EventBridge vs Kinesis vs MSK?
12. How do you design DR across regions on AWS?
13. How do you control AWS cost in a high-traffic platform?
14. How do you design a secure AWS landing zone?
15. How do you observe and audit production AWS infrastructure?

## Official Reference Anchors

- AWS Well-Architected Framework: https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html
- Amazon EKS User Guide: https://docs.aws.amazon.com/eks/latest/userguide/what-is-eks.html
- Amazon ECS Developer Guide: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/Welcome.html
- Elastic Load Balancing User Guide: https://docs.aws.amazon.com/elasticloadbalancing/latest/userguide/what-is-load-balancing.html
- Amazon RDS User Guide: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Welcome.html
- AWS IAM User Guide: https://docs.aws.amazon.com/IAM/latest/UserGuide/introduction.html
- AWS KMS Developer Guide: https://docs.aws.amazon.com/kms/latest/developerguide/overview.html
- Amazon ElastiCache User Guide: https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/WhatIs.html

