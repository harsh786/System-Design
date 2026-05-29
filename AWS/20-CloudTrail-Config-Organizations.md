# CloudTrail, Config & Organizations - Governance & Compliance Guide

---

## 1. AWS CloudTrail

### Overview
- **What:** Records all API calls (who did what, when, from where) across AWS account
- **Enabled by default:** 90 days of management event history (free, console viewable)
- **Trail:** Delivers events to S3 bucket (and optionally CloudWatch Logs) for long-term retention
- **Scope:** Per-region or organization trail (all accounts, all regions)
- **Pricing:** First management trail per region = free delivery to S3. Additional trails: $2/100K events

### Event Types
| Type | What | Examples | Default |
|------|------|----------|---------|
| Management Events | Control plane operations | CreateBucket, RunInstances, CreateUser | ON (free) |
| Data Events | Data plane operations | S3 GetObject/PutObject, Lambda Invoke, DynamoDB GetItem | OFF (paid) |
| Insights Events | Unusual activity detection | Burst of API calls, error rate spikes | OFF (paid) |

### Trail Configuration
```yaml
Trail:
  Name: org-trail
  IsOrganizationTrail: true      # All accounts in org
  IsMultiRegionTrail: true       # All regions
  S3BucketName: audit-trail-bucket
  CloudWatchLogsLogGroupArn: arn:...   # Real-time search
  KMSKeyId: arn:aws:kms:...      # Encrypt log files
  EnableLogFileValidation: true   # Digest files for integrity
  
  EventSelectors:
    - ReadWriteType: All
      IncludeManagementEvents: true
      DataResources:
        - Type: AWS::S3::Object
          Values: ["arn:aws:s3:::sensitive-bucket/"]
        - Type: AWS::Lambda::Function
          Values: ["arn:aws:lambda:*:*:function:*"]
```

### CloudTrail Lake
- **What:** Managed data lake for CloudTrail events (SQL query interface)
- **Retention:** 7 years (configurable)
- **Query:** SQL-like syntax to search events
- **Federation:** Query from external sources (non-AWS events)
- **Use case:** Long-term audit queries, cross-account analysis, compliance reporting
```sql
SELECT eventTime, userIdentity.arn, eventName, requestParameters
FROM event_data_store_id
WHERE eventName = 'DeleteBucket'
  AND eventTime > '2024-01-01'
ORDER BY eventTime DESC
```

### CloudTrail Insights
- Detects unusual patterns in API call volume or error rates
- **Write Insights:** Unusual write API activity (e.g., burst of DeleteObject calls)
- **Error rate Insights:** Unusual increase in API error responses
- Baseline: Normal activity pattern over 7 days
- Alert: CloudTrail → EventBridge → SNS/Lambda

### Security Best Practices
1. **Organization trail:** Single trail for all accounts (centralized audit)
2. **S3 bucket policy:** Restrict access (only trail can write, security team can read)
3. **Log file validation:** Enable digest files (detect tampering)
4. **Encryption:** KMS CMK (audit key access via KMS CloudTrail events)
5. **Access:** S3 Object Lock (WORM) on audit bucket (prevent deletion)
6. **Alerting:** CloudWatch Logs → Metric Filters → Alarms for critical events
7. **Lifecycle:** S3 lifecycle → Glacier after 90 days (cost optimization)

### Key CloudTrail Alerts to Configure
| Alert | Pattern (Metric Filter) |
|-------|------------------------|
| Root account login | `{ $.userIdentity.type = "Root" }` |
| Console login without MFA | `{ $.eventName = "ConsoleLogin" && $.additionalEventData.MFAUsed = "No" }` |
| IAM policy changes | `{ $.eventName = "Put*Policy" || $.eventName = "Attach*" || $.eventName = "Detach*" }` |
| Security group changes | `{ $.eventName = "AuthorizeSecurityGroup*" || $.eventName = "RevokeSecurityGroup*" }` |
| Network changes (VPC, subnet, route) | `{ $.eventName = "Create*" || $.eventName = "Delete*" && $.eventSource = "ec2.amazonaws.com" }` |
| S3 bucket policy changes | `{ $.eventName = "PutBucketPolicy" || $.eventName = "DeleteBucketPolicy" }` |
| Failed console logins | `{ $.eventName = "ConsoleLogin" && $.errorMessage = "Failed authentication" }` |
| KMS key deletion | `{ $.eventName = "DisableKey" || $.eventName = "ScheduleKeyDeletion" }` |

---

## 2. AWS Config

### Overview
- **What:** Continuous recording of AWS resource configurations and compliance evaluation
- **Records:** Configuration changes over time (configuration timeline)
- **Evaluates:** Compliance against rules (managed or custom)
- **Remediates:** Auto-fix non-compliant resources
- **Scope:** Per-region, per-account (or organization-wide via aggregator)
- **Pricing:** $0.003 per configuration item recorded, $0.001 per rule evaluation

### How It Works
```
Resource changes → Config records configuration item → Evaluates against rules
  → Compliant: ✓
  → Non-compliant: ✗ → Notification (SNS) → Auto-remediation (SSM)
```

### Configuration Items
- Stored per resource: Metadata, attributes, relationships, configuration, events
- **Configuration History:** Timeline of changes for any resource
- **Configuration Snapshot:** Complete configuration at point in time (S3 delivery)
- **Configuration Stream:** Real-time stream of changes (SNS notification)

### AWS Config Rules

#### Managed Rules (330+ pre-built)
| Category | Example Rules |
|----------|--------------|
| Security | s3-bucket-public-read-prohibited, encrypted-volumes, iam-password-policy |
| Compute | ec2-instance-no-public-ip, restricted-ssh, approved-amis-by-id |
| Database | rds-multi-az-support, rds-storage-encrypted, dynamodb-pitr-enabled |
| Network | vpc-flow-logs-enabled, restricted-common-ports, vpc-sg-open-only-to-authorized-ports |
| Storage | s3-bucket-versioning-enabled, s3-bucket-ssl-requests-only |
| Logging | cloud-trail-enabled, cloudwatch-log-group-encrypted |
| Tagging | required-tags (enforce tag compliance) |

#### Custom Rules
- **Lambda-based:** Your Lambda function evaluates compliance
- **Guard-based:** AWS CloudFormation Guard policy-as-code (declarative)
```
# Guard rule example
rule s3_encrypted {
  AWS::S3::Bucket {
    BucketEncryption.ServerSideEncryptionConfiguration[*].ServerSideEncryptionByDefault.SSEAlgorithm == "aws:kms"
  }
}
```

#### Evaluation Triggers
- **Change-triggered:** Evaluated when resource changes (real-time)
- **Periodic:** Evaluated on schedule (1, 3, 6, 12, 24 hours)
- **Hybrid:** Both (change + periodic catch-up)

### Remediation
- **Auto-remediation:** Non-compliant → SSM Automation document → fixes resource
- **Manual remediation:** Generate remediation action, human approves
- **SSM Documents examples:**
  - AWS-DisableS3BucketPublicReadWrite (remove public access)
  - AWS-EnableS3BucketEncryption (enable default encryption)
  - AWS-StopEC2Instance (stop non-compliant instance)
- **Remediation retry:** Configure retries and concurrency

### Config Aggregator
- **Multi-account, multi-region view:** Centralized compliance dashboard
- **Sources:** Organization (all accounts) or specific accounts
- **Aggregator account:** Usually security/audit account
- **Use case:** CISO dashboard showing compliance across all accounts

### Conformance Packs
- **What:** Collection of Config rules + remediation bundled as a package
- **Pre-built:** AWS provides packs for frameworks (CIS, PCI-DSS, HIPAA, SOC2)
- **Custom:** Create your own organizational standards pack
- **Deployment:** Deploy across organization via CloudFormation StackSets

---

## 3. AWS Organizations

### Overview
- **What:** Central management of multiple AWS accounts
- **Structure:** Root → Organizational Units (OUs) → Accounts
- **Benefits:** Consolidated billing, centralized policy, account factory
- **Management account:** Pays all bills, creates accounts, manages organization
- **No additional charge** for Organizations itself

### Organization Structure
```
Root
├── Management Account (payer, governance)
├── Security OU
│   ├── Log Archive Account (centralized logs)
│   └── Security Tooling Account (GuardDuty, Security Hub)
├── Infrastructure OU
│   ├── Shared Services Account (CI/CD, DNS, networking)
│   └── Network Account (Transit Gateway, Direct Connect)
├── Workloads OU
│   ├── Production OU
│   │   ├── App A Production
│   │   └── App B Production
│   └── Non-Production OU
│       ├── Development Accounts
│       └── Staging Accounts
├── Sandbox OU
│   └── Developer sandbox accounts
└── Suspended OU (for decommissioned accounts)
```

### Service Control Policies (SCPs)
- **What:** Guardrails on what actions accounts/OUs can perform (permission boundaries)
- **Does NOT grant permissions** (only restricts). IAM policies still needed
- **Inheritance:** Applied to OU → all accounts below inherit
- **Does not affect management account** (management account immune to SCPs)

#### SCP Examples
```json
// Deny leaving organization
{
  "Effect": "Deny",
  "Action": "organizations:LeaveOrganization",
  "Resource": "*"
}

// Deny disabling CloudTrail
{
  "Effect": "Deny",
  "Action": ["cloudtrail:StopLogging", "cloudtrail:DeleteTrail"],
  "Resource": "*"
}

// Restrict regions (only allow us-east-1, eu-west-1)
{
  "Effect": "Deny",
  "NotAction": [
    "iam:*", "organizations:*", "support:*", "sts:*"
  ],
  "Resource": "*",
  "Condition": {
    "StringNotEquals": {
      "aws:RequestedRegion": ["us-east-1", "eu-west-1"]
    }
  }
}

// Deny root user actions
{
  "Effect": "Deny",
  "Action": "*",
  "Resource": "*",
  "Condition": {
    "StringLike": {
      "aws:PrincipalArn": "arn:aws:iam::*:root"
    }
  }
}

// Require encryption on S3
{
  "Effect": "Deny",
  "Action": "s3:PutObject",
  "Resource": "*",
  "Condition": {
    "StringNotEquals": {
      "s3:x-amz-server-side-encryption": "aws:kms"
    }
  }
}
```

### AWS Control Tower
- **What:** Automated landing zone setup with best-practice multi-account architecture
- **Account Factory:** Self-service account provisioning (pre-configured)
- **Guardrails:** Preventive (SCP-based) + Detective (Config rule-based)
- **Dashboard:** Compliance status across all enrolled accounts
- **Customizations:** Lifecycle events → Lambda → customize new accounts

### Organization-Wide Services
| Service | Delegated Admin | Purpose |
|---------|----------------|---------|
| CloudTrail | Organization trail | Centralized audit logging |
| Config | Delegated admin | Organization-wide compliance |
| GuardDuty | Delegated admin | Threat detection all accounts |
| Security Hub | Delegated admin | Centralized security findings |
| IAM Access Analyzer | Per-account | Cross-account access analysis |
| Backup | Delegated admin | Organization backup policies |
| RAM | Sharing via org | Share resources across accounts |

### Resource Access Manager (RAM)
- **Share resources across accounts/OUs:**
  - VPC Subnets (shared networking)
  - Transit Gateway
  - Route 53 Resolver Rules
  - License Manager configurations
  - Prefix Lists
- **Benefit:** Avoid resource duplication, centralize shared infrastructure

---

## 4. Additional Governance Services

### AWS Security Hub
- **Central security dashboard:** Aggregates findings from GuardDuty, Inspector, Macie, Config, Firewall Manager
- **Standards:** Automated checks against CIS, PCI-DSS, AWS Foundational Best Practices
- **Findings format:** AWS Security Finding Format (ASFF) - normalized across sources
- **Automated actions:** EventBridge rules → Lambda/SSM for auto-remediation

### Amazon GuardDuty
- **Intelligent threat detection:** Analyzes CloudTrail, VPC Flow Logs, DNS logs, EKS audit logs
- **Findings:** Crypto mining, compromised instances, unusual API calls, data exfiltration
- **ML-based:** Learns normal patterns, alerts on anomalies
- **Multi-account:** Delegated admin manages all accounts

### Amazon Macie
- **Sensitive data discovery:** Scans S3 for PII, PHI, financial data, credentials
- **Classification:** Uses ML + pattern matching
- **Alerts:** Findings when sensitive data found in unexpected locations
- **Use case:** GDPR compliance, data governance, accidental data exposure

### AWS Inspector
- **Vulnerability scanning:** EC2, ECR containers, Lambda functions
- **Checks:** CVEs, network reachability, OS patching, runtime vulnerabilities
- **Continuous:** Auto-scans on deploy, package updates, new CVEs published
- **Findings:** Severity-rated, remediation guidance provided

### AWS Audit Manager
- **Continuous compliance evidence collection**
- **Frameworks:** Pre-built (SOC 2, GDPR, HIPAA, PCI-DSS, CIS)
- **Evidence:** Automated collection from Config, CloudTrail, Security Hub
- **Reports:** Audit-ready reports for external auditors
- **Use case:** Reduce manual evidence collection for compliance audits

---

## 5. Governance Architecture Patterns

### Centralized Logging
```
All Accounts → CloudTrail → S3 (Log Archive Account)
All Accounts → VPC Flow Logs → CloudWatch Logs → S3
All Accounts → Config → S3 (Log Archive Account)
All Accounts → GuardDuty findings → Security Account

S3 Bucket Policy: Only trail can write. Immutable (Object Lock)
Lifecycle: 90 days Standard → Glacier → 7 years Deep Archive
Access: Security team read-only. Audit queries via Athena/CloudTrail Lake
```

### Preventive + Detective Controls
```
Preventive (stop bad actions):
  - SCPs: Block disabling security services, restrict regions
  - IAM Permission Boundaries: Limit developer max permissions
  - S3 Block Public Access: Organization-wide setting
  - VPC: No internet gateway in production VPC

Detective (find violations after):
  - Config Rules: Continuous compliance checks
  - GuardDuty: Threat detection
  - Security Hub: Aggregated security posture
  - CloudTrail: Audit trail of all actions
  - Access Analyzer: Find unintended external access

Responsive (auto-fix):
  - Config auto-remediation (SSM Automation)
  - Security Hub → EventBridge → Lambda (isolate compromised instance)
  - GuardDuty finding → Step Functions → quarantine workflow
```

### Tagging Strategy & Enforcement
```
Required Tags (via Config rule + SCP):
  - Environment: production, staging, development
  - Team: platform, payments, orders
  - CostCenter: CC-1234
  - DataClassification: public, internal, confidential, restricted
  - Compliance: pci, hipaa, sox, none

Enforcement:
  Config Rule: required-tags (detect non-compliant)
  SCP: Deny resource creation without required tags
  Tag Policy (Organizations): Define allowed values per key
  
Cost allocation:
  - Activate cost allocation tags in billing
  - AWS Cost Explorer: Group by team, environment
  - Budget alerts per cost center
```

---

## 6. Scenario-Based Interview Questions

### Q1: Design governance for a 50-account AWS organization
**Answer:**
```
Organization Structure:
  Root (SCP: deny leave org, deny disable security services)
  ├── Security OU (SCP: restrict to security services only)
  │   ├── Log Archive (CloudTrail, Config, Flow Logs destination)
  │   └── Security Tooling (GuardDuty admin, Security Hub, Macie)
  ├── Infrastructure OU (SCP: no workloads, only shared infra)
  │   ├── Network (Transit Gateway, Direct Connect, Route 53)
  │   └── Shared Services (CI/CD, ECR, artifact repos)
  ├── Workloads OU
  │   ├── Production (SCP: deny delete*, require encryption, restrict regions)
  │   └── Non-Prod (SCP: restrict expensive instances, no production data)
  └── Sandbox (SCP: budget cap $500/month, no connectivity to prod)

Controls:
  - Organization CloudTrail (all accounts, all regions)
  - Config Rules via conformance packs (deployed to all)
  - GuardDuty enabled organization-wide
  - Security Hub aggregating all findings
  - SCPs preventing disabling of any security control
  - Budget alerts at account and OU level
  - Tag policies enforcing required tags
  
Account provisioning:
  - Control Tower Account Factory (automated)
  - Baseline: CloudTrail, Config, GuardDuty auto-enabled
  - Network: Auto-attach to Transit Gateway
  - IAM: Federated access only (no IAM users in workload accounts)
```

### Q2: Investigate unauthorized access — someone deleted production database
**Answer:**
```
Investigation steps:

1. CloudTrail (who/when/where):
   Search for: DeleteDBInstance or DeleteDBCluster
   Find: userIdentity.arn, sourceIPAddress, eventTime, userAgent
   
2. Context:
   - Was it a role? → Who assumed it? (AssumeRole event in CloudTrail)
   - Was it from known IP? → VPN vs unknown location
   - Was it programmatic (CLI) or console?
   - What time? (business hours or 3 AM?)

3. Impact assessment:
   - Config: Show configuration timeline (what was the DB state)
   - Automated backups: Can we restore? (RDS automated backups, snapshots)
   - Data events: Were there unusual reads before deletion? (data exfiltration)

4. Containment:
   - Revoke the compromised credentials (deactivate access keys, revoke sessions)
   - If role: Update trust policy to deny assume
   - Check for persistence (new IAM users? new access keys? Lambda backdoor?)

5. Recovery:
   - Restore from latest snapshot (RDS point-in-time recovery)
   - Apply binary logs/WAL for transactions between snapshot and deletion
   
6. Prevention:
   - SCP: Deny DeleteDBInstance without specific condition (requires approval tag)
   - Config Rule: rds-instance-deletion-protection-enabled
   - RDS: Enable deletion protection on all prod databases
   - IAM: Remove direct delete permissions, require MFA for destructive actions
   - Backup: Cross-account backup copy (even if source account compromised)
```

### Q3: How to enforce compliance with PCI-DSS in AWS?
**Answer:**
```
Framework: PCI-DSS (Payment Card Industry Data Security Standard)

Architecture:
  Cardholder Data Environment (CDE): Isolated account/VPC
  - No internet access (private subnets only)
  - Network segmentation (security groups, NACLs)
  - Encrypted at rest (KMS CMK) and in transit (TLS 1.2+)
  
Controls:
  Preventive:
  - SCPs: CDE account restricted to approved services only
  - SG: Restrict all inbound, explicit outbound rules only
  - KMS: Key policy limits access to specific roles
  - IAM: Least privilege, no wildcard permissions
  
  Detective:
  - Config: PCI-DSS conformance pack (50+ rules)
  - Security Hub: PCI-DSS standard enabled
  - GuardDuty: Detect unusual data access patterns
  - Macie: Continuous scan for exposed card data (PAN, CVV)
  - VPC Flow Logs: Capture all network traffic for forensics
  
  Audit:
  - CloudTrail: All events, log integrity validation
  - AWS Artifact: AWS PCI-DSS AOC (Attestation of Compliance)
  - Audit Manager: Automated evidence collection for QSA
  - Quarterly: Vulnerability scans (Inspector)
  - Annual: Penetration testing (notify AWS)
  
  Logging (Requirement 10):
  - Retain audit logs: 1 year (3 months immediately available)
  - Object Lock on log buckets (immutable)
  - Cross-account (CDE account can't modify its own logs)
```

### Q4: Config rules report 500 non-compliant resources. How to prioritize remediation?
**Answer:**
```
Prioritization framework:

1. CRITICAL (fix immediately):
   - Public S3 buckets with data (data exposure risk)
   - Security groups with 0.0.0.0/0 on sensitive ports (3306, 5432, 22)
   - Unencrypted resources with sensitive data
   - IAM users without MFA
   
2. HIGH (fix within 1 week):
   - Resources without encryption at rest
   - Disabled logging (CloudTrail, Flow Logs)
   - Deletion protection disabled on production DBs
   - Missing backups
   
3. MEDIUM (fix within 1 month):
   - Missing tags (cost governance, but not security risk)
   - Non-current runtime versions (need planned update)
   - Suboptimal configurations (single-AZ non-critical resources)
   
4. LOW (track, fix during maintenance):
   - Unused resources (cost, not security)
   - Minor configuration drift

Auto-remediation (safe to auto-fix):
  - Enable S3 default encryption
  - Enable EBS encryption
  - Remove overly permissive SG rules
  - Enable deletion protection
  
Manual remediation (needs review):
  - IAM policy changes (might break workloads)
  - Network changes (might affect connectivity)
  - Tag compliance (need team input for correct values)
  
Process:
  - Config → Security Hub (centralized view with severity)
  - Weekly compliance review meeting
  - Assign owners per account/OU
  - Track trend: Non-compliant count should decrease week over week
```

### Q5: How does the effective permission model work with SCPs + IAM?
**Answer:**
```
Effective permissions = Intersection of:
  1. SCP (Organization level guardrail - max possible)
  2. IAM Permission Boundary (per-user/role max)
  3. IAM Policy (what's granted - identity or resource policy)
  4. Session Policy (if assuming role with restriction)
  5. Resource Policy (what the resource allows)

Evaluation logic:
  ALLOW in IAM policy
  AND NOT DENY in any SCP above the account
  AND NOT DENY in Permission Boundary
  AND NOT DENY in Session Policy
  AND NOT explicit DENY in any policy
  = ALLOWED

Example:
  SCP allows: ec2:*, s3:*, lambda:* (deny everything else)
  Permission Boundary: s3:*, lambda:* (no ec2)
  IAM Policy: s3:GetObject, s3:PutObject, ec2:RunInstances
  
  Effective: Only s3:GetObject and s3:PutObject
    - ec2:RunInstances: Denied by Permission Boundary
    - s3:GetObject: Allowed in all three ✓
    - s3:PutObject: Allowed in all three ✓

Key insight for Staff/Architect:
  - SCPs are DENY-only in practice (use to block, not to grant)
  - Management account is NEVER affected by SCPs
  - Delegated admin pattern: Security account manages org security services
  - Break-glass: Special role/account with elevated SCPs for emergencies
```

