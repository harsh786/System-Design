# Secrets Management, KMS & Encryption - Complete Guide

---

## 1. AWS KMS (Key Management Service)

### Overview
- **What:** Managed service to create and control encryption keys
- **FIPS 140-2 Level 3:** Hardware Security Modules (HSMs) validated
- **Integrated:** 100+ AWS services use KMS for encryption
- **Regional:** Keys are region-specific (can be multi-region)
- **Pricing:** $1/month per key + $0.03 per 10,000 API calls

### Key Types
| Type | Managed By | Rotation | Use Case |
|------|-----------|----------|----------|
| AWS Owned Keys | AWS (invisible to you) | AWS manages | Default S3 encryption (SSE-S3) |
| AWS Managed Keys | AWS (visible, aws/service) | Auto yearly | Per-service default (aws/rds, aws/ebs) |
| Customer Managed Keys (CMK) | You | Manual or auto (yearly) | Full control, audit, cross-account |
| External Key Material | You (import your own) | Manual only | Regulatory requirement to control key material |

### Key Specs
| Spec | Algorithm | Use Case |
|------|-----------|----------|
| SYMMETRIC_DEFAULT | AES-256-GCM | Encrypt/decrypt data (most common) |
| RSA_2048/3072/4096 | RSA | Encrypt/sign (non-AWS systems) |
| ECC_NIST_P256/384/521 | Elliptic Curve | Digital signatures |
| ECC_SECG_P256K1 | secp256k1 | Blockchain |
| HMAC_256/384/512 | HMAC | Message authentication |
| SM2 (China regions) | SM2 | Chinese national standard |

### Envelope Encryption
```
Problem: KMS can only encrypt up to 4 KB directly

Solution: Envelope encryption
  1. Application calls KMS: GenerateDataKey
  2. KMS returns: Plaintext data key + Encrypted data key (encrypted with CMK)
  3. Application uses PLAINTEXT data key to encrypt data (AES-256 locally)
  4. Application stores: Encrypted data + Encrypted data key (together)
  5. Application discards plaintext data key from memory
  
Decryption:
  1. Application sends encrypted data key to KMS: Decrypt
  2. KMS returns plaintext data key
  3. Application decrypts data locally with plaintext data key
  
Why? 
  - Large data encrypted locally (fast, no network round-trip per record)
  - Only 4KB data key sent to KMS (not your 10GB file)
  - Data key encrypted by CMK (key hierarchy: CMK → data key → data)
```

### Key Policies & Access Control
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "Root account has full access",
      "Effect": "Allow",
      "Principal": {"AWS": "arn:aws:iam::123456789012:root"},
      "Action": "kms:*",
      "Resource": "*"
    },
    {
      "Sid": "Admins can manage key",
      "Effect": "Allow",
      "Principal": {"AWS": "arn:aws:iam::123456789012:role/KeyAdmin"},
      "Action": ["kms:Create*", "kms:Describe*", "kms:Enable*", "kms:List*",
                 "kms:Put*", "kms:Update*", "kms:Revoke*", "kms:Disable*",
                 "kms:Get*", "kms:Delete*", "kms:ScheduleKeyDeletion"],
      "Resource": "*"
    },
    {
      "Sid": "Users can use key for encryption",
      "Effect": "Allow",
      "Principal": {"AWS": "arn:aws:iam::123456789012:role/AppRole"},
      "Action": ["kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey"],
      "Resource": "*"
    }
  ]
}
```

### Cross-Account Key Sharing
```
Account A (key owner):
  Key Policy: Allow Account B's role to use key
  
Account B (user):
  IAM Policy: Allow kms:Decrypt on Account A's key ARN
  
Both required: Key policy (resource-based) + IAM policy (identity-based)
```

### Multi-Region Keys
- **What:** Same key material replicated to multiple regions
- **Use case:** Encrypt in one region, decrypt in another (DR, multi-region apps)
- **Primary key → Replica keys** (same key ID, different ARNs)
- **NOT independent copies:** Changes to primary propagate to replicas
- **Use case:** DynamoDB Global Tables encryption, cross-region S3 replication with CMK

### Key Rotation
- **Automatic rotation (CMK):** New key material yearly. Old material kept for decryption
- **Manual rotation:** Create new key, update aliases, re-encrypt data with new key
- **Imported keys:** Must rotate manually (automatic rotation not supported)
- **Alias:** Point alias to new key (application uses alias, transparent rotation)

### Key Deletion
- **Waiting period:** 7-30 days (default 30). Can cancel during this period
- **Danger:** If key deleted, all data encrypted with it is PERMANENTLY irrecoverable
- **Best practice:** Disable key first, monitor for usage (CloudTrail), then schedule deletion
- **Detection:** CloudWatch alarm on key usage during waiting period

---

## 2. AWS Secrets Manager

### Overview
- **What:** Store, rotate, and retrieve secrets (database credentials, API keys, tokens)
- **Rotation:** Automatic rotation via Lambda (built-in for RDS, Redshift, DocumentDB)
- **Versioning:** AWSCURRENT, AWSPREVIOUS, AWSPENDING labels
- **Encryption:** Every secret encrypted with KMS key
- **Pricing:** $0.40/secret/month + $0.05 per 10,000 API calls

### How Rotation Works
```
1. Create Secret: Store DB credentials
2. Configure Rotation: Every 30 days + Lambda rotation function
3. Rotation triggers (Lambda):
   a. createSecret: Generate new password, store as AWSPENDING
   b. setSecret: Update password in database (ALTER USER)
   c. testSecret: Verify new credentials work (connect and query)
   d. finishSecret: Move AWSPENDING → AWSCURRENT, old → AWSPREVIOUS
   
4. Application calls GetSecretValue → always gets AWSCURRENT

Application impact: Brief moment where old password might fail
  Solution: Application caches secret, refreshes on auth failure
  OR: Multi-user rotation (alternating between user-1 and user-2)
```

### Multi-User Rotation
```
Traditional (single-user):
  - Secret: user/password
  - Problem: Brief interruption during password change
  
Multi-user (alternating):
  - Secret: user1/password1 AND user2/password2
  - Rotation: Update user2 password → test → switch AWSCURRENT to user2
  - Never a gap: user1 active while user2 rotates, then swap
  - Best for: Production databases with zero-tolerance for auth failures
```

### Cross-Account & Cross-Region
- **Cross-account:** Resource policy on secret → other account can GetSecretValue
- **Cross-region replication:** Automatically replicate secret to other regions
  - DR scenarios: Application in DR region reads local replica
  - Reduces latency: Read from nearest region

### Secrets Manager vs SSM Parameter Store
| Feature | Secrets Manager | SSM Parameter Store |
|---------|----------------|---------------------|
| Rotation | Built-in (Lambda-based) | Manual (no built-in rotation) |
| Cost | $0.40/secret/month | Free (Standard) or $0.05/adv parameter |
| Encryption | Always encrypted (KMS) | Optional (SecureString with KMS) |
| Size | Up to 64 KB | 4 KB (Standard) or 8 KB (Advanced) |
| Cross-region replication | Yes | No |
| Versioning | Yes (labels) | Yes (history) |
| **Use for** | DB credentials, API keys needing rotation | Config values, feature flags, non-sensitive |

---

## 3. SSM Parameter Store

### Overview
- **What:** Hierarchical storage for configuration data and secrets
- **Free tier:** Standard parameters (up to 10,000 per account, 4 KB each)
- **Advanced:** $0.05/parameter/month, 8 KB, policies, higher throughput
- **Hierarchy:** /app/prod/db/password (path-based, IAM can scope to path)

### Parameter Types
| Type | Description | Example |
|------|-------------|---------|
| String | Plain text | `ami-12345678` |
| StringList | Comma-separated | `us-east-1,us-west-2,eu-west-1` |
| SecureString | Encrypted with KMS | `MyS3cr3tP@ssw0rd` |

### Hierarchy & Access Pattern
```
/myapp/
  /myapp/production/
    /myapp/production/db/host → rds.endpoint.amazonaws.com
    /myapp/production/db/password → (SecureString) encrypted
    /myapp/production/api/key → (SecureString) encrypted
    /myapp/production/feature/dark-mode → true
  /myapp/staging/
    /myapp/staging/db/host → staging-rds.endpoint.amazonaws.com
    ...

IAM Policy:
  Allow ssm:GetParametersByPath on /myapp/production/* → only production access
  Allow ssm:GetParametersByPath on /myapp/staging/* → only staging access
```

### Parameter Store Features
- **Policies (Advanced):** TTL (expire parameter), notification (alert before expiry)
- **Labels:** Version labels (like "production", "v2")
- **Change notification:** EventBridge events on parameter change
- **GetParametersByPath:** Retrieve all parameters under a path (efficient bulk fetch)
- **Integration:** ECS task definitions, CloudFormation, Lambda environment variables

---

## 4. AWS CloudHSM

### Overview
- **What:** Dedicated Hardware Security Module in AWS cloud
- **Compliance:** FIPS 140-2 Level 3 (KMS is also Level 3, but multi-tenant)
- **Control:** You control the HSM (AWS has NO access to your keys)
- **Use case:** Regulatory requirements for dedicated HSM, custom key store for KMS

### KMS vs CloudHSM
| | KMS | CloudHSM |
|--|---|---|
| Tenancy | Multi-tenant (shared) | Single-tenant (dedicated) |
| Control | AWS manages HSM | You manage HSM (init, users, keys) |
| HA | AWS handles | You deploy cluster (2+ HSMs in 2+ AZs) |
| Integration | 100+ AWS services native | Custom (PKCS#11, JCE, CNG) + KMS Custom Key Store |
| Compliance | FIPS 140-2 Level 3 | FIPS 140-2 Level 3 |
| Access | IAM + Key Policy | HSM-level users (quorum auth) |
| Cost | $1/key/month | $1.60/HSM/hour (~$1,150/month) |
| **Use** | 99% of use cases | Contractual/regulatory single-tenant requirement |

### KMS Custom Key Store
- Link CloudHSM cluster to KMS
- KMS operations (Encrypt, Decrypt, GenerateDataKey) execute on YOUR HSMs
- Benefit: KMS API simplicity + CloudHSM hardware control
- Use case: Use KMS-integrated services (S3, EBS) but keys stored in your HSM

---

## 5. Encryption Patterns

### Encryption at Rest
| Service | Default | Customer Managed CMK | Client-Side |
|---------|---------|---------------------|-------------|
| S3 | SSE-S3 (auto) | SSE-KMS | CSE (encrypt before upload) |
| EBS | Not encrypted | KMS (enable at volume/account level) | N/A |
| RDS | Not encrypted (enable at creation) | KMS | N/A |
| DynamoDB | AWS owned key (auto) | KMS CMK | Client-side (attribute encryption) |
| Lambda env vars | AWS managed key | KMS CMK (encrypt helper) | SDK-encrypted |
| SQS | Not encrypted | SSE-KMS or SSE-SQS | N/A |
| Kinesis | Not encrypted | SSE-KMS | N/A |
| EFS | Not encrypted | KMS | N/A |

### Encryption in Transit
- **TLS 1.2+ everywhere** (AWS SDK uses TLS by default)
- **S3:** Bucket policy to deny unencrypted connections (`"aws:SecureTransport": "false"`)
- **RDS:** Force SSL (rds.force_ssl = 1)
- **ALB/NLB:** TLS termination with ACM certificate
- **mTLS (mutual TLS):** Client and server authenticate each other (ALB supports)
- **VPC:** Traffic between VPCs uses TLS or VPN/PrivateLink (already encrypted)

### Client-Side Encryption
```python
# AWS Encryption SDK (client-side envelope encryption)
import aws_encryption_sdk

client = aws_encryption_sdk.EncryptionSDKClient()
kms_provider = aws_encryption_sdk.StrictAwsKmsMasterKeyProvider(
    key_ids=["arn:aws:kms:us-east-1:123:key/abc-123"]
)

# Encrypt
ciphertext, header = client.encrypt(
    source=plaintext_data,
    key_provider=kms_provider,
    encryption_context={"purpose": "user-pii", "tenant": "acme"}
)

# Decrypt (encryption context must match)
plaintext, header = client.decrypt(
    source=ciphertext,
    key_provider=kms_provider
)
```

### Encryption Context
- **What:** Key-value pairs associated with encrypt/decrypt operations
- **Purpose:** Additional authenticated data (AAD) — must match on decrypt
- **Audit:** Logged in CloudTrail (see what was encrypted/decrypted and why)
- **Example:** `{"tenant": "acme", "dataType": "PII"}` — decrypt fails without same context
- **Use case:** Multi-tenant isolation (each tenant's data has their tenant ID in context)

---

## 6. Secrets Management Patterns

### Application Secret Retrieval
```python
# Lambda / ECS / EC2 application pattern
import boto3
from functools import lru_cache

secrets_client = boto3.client('secretsmanager')

@lru_cache(maxsize=1)  # Cache to avoid repeated API calls
def get_db_credentials():
    response = secrets_client.get_secret_value(SecretId='prod/db/credentials')
    return json.loads(response['SecretString'])

# Usage
creds = get_db_credentials()
connection = psycopg2.connect(
    host=creds['host'],
    user=creds['username'],
    password=creds['password']
)
```

### ECS + Secrets Manager Integration
```json
{
  "containerDefinitions": [{
    "name": "app",
    "image": "my-app:latest",
    "secrets": [
      {
        "name": "DB_PASSWORD",
        "valueFrom": "arn:aws:secretsmanager:us-east-1:123:secret:prod/db/password"
      },
      {
        "name": "API_KEY",
        "valueFrom": "arn:aws:ssm:us-east-1:123:parameter/prod/api/key"
      }
    ]
  }]
}
```
- ECS agent retrieves secret at task startup
- Injected as environment variable in container
- **Limitation:** Value is static for task lifetime (doesn't update if rotated)
- **Alternative:** Application fetches at runtime with caching + refresh on auth failure

### Kubernetes External Secrets
```yaml
# External Secrets Operator (ESO) → syncs AWS secrets to K8s secrets
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: db-credentials
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secret-store
    kind: ClusterSecretStore
  target:
    name: db-credentials  # K8s secret name
  data:
    - secretKey: password
      remoteRef:
        key: prod/db/credentials  # AWS Secrets Manager secret
        property: password        # JSON key within secret
```

### Multi-Account Secrets Architecture
```
Central Security Account:
  - Secrets Manager: Stores shared secrets (DB passwords for shared services)
  - KMS: CMK for secret encryption
  - Resource policy: Allow workload account roles to GetSecretValue
  
Workload Accounts:
  - Own secrets (application-specific API keys)
  - Cross-account access to shared secrets (via resource policy + IAM role)
  - Rotation: Each account has own Lambda rotation function
  
Audit:
  - CloudTrail: All GetSecretValue calls logged (who accessed what, when)
  - Config Rule: Secrets not rotated in > 90 days = non-compliant
  - GuardDuty: Alert on unusual secret access patterns
```

---

## 7. Scenario-Based Interview Questions

### Q1: Design secret management for 200-microservice platform
**Answer:**
```
Architecture:
  Storage: AWS Secrets Manager (DB creds, API keys) + SSM Parameter Store (config)
  
  Hierarchy:
    Secrets Manager: /{environment}/{service}/{secret-name}
      /production/order-service/db-credentials
      /production/payment-service/stripe-api-key
    
    Parameter Store: /{environment}/{service}/{config-name}  
      /production/order-service/feature-flags
      /production/order-service/connection-pool-size

  Access control:
    IAM role per service (least privilege):
      order-service-role → can only read /production/order-service/*
      No cross-service secret access
      
  Rotation:
    DB credentials: Auto-rotation every 30 days (multi-user for zero downtime)
    API keys: Custom Lambda rotation (calls provider API to regenerate)
    TLS certificates: ACM (auto-renewal) or custom Lambda
    
  Application pattern:
    - SDK with caching (AWS SDK caches for 5 min, configurable)
    - Refresh on authentication failure (handles rotation gracefully)
    - NO environment variables for sensitive secrets (visible in ECS console)
    - Use init container / sidecar for K8s (External Secrets Operator)
    
  Monitoring:
    - CloudTrail: All access audited
    - CloudWatch alarm: Secret access from unexpected roles
    - Config rule: Secrets > 90 days without rotation = alert
    - Metric: Track rotation failures (Lambda DLQ)
```

### Q2: KMS key accidentally deleted. What happens and how to prevent?
**Answer:**
```
What happens:
  - All data encrypted with that key is PERMANENTLY LOST (irrecoverable)
  - S3 objects: unreadable
  - EBS volumes: unmountable
  - RDS: unreadable
  
Prevention layers:
  1. Key deletion waiting period: 30 days (maximum)
     - During waiting: Key is disabled, CloudTrail shows any usage
     - If usage detected → cancel deletion immediately
     
  2. CloudWatch alarm:
     - Monitor: "kms:ScheduleKeyDeletion" in CloudTrail
     - Alert: P1 to security team immediately
     
  3. SCP (Organization-level):
     {
       "Effect": "Deny",
       "Action": "kms:ScheduleKeyDeletion",
       "Resource": "*",
       "Condition": {
         "StringNotLike": {
           "aws:PrincipalArn": "arn:aws:iam::*:role/BreakGlass"
         }
       }
     }
     Only break-glass role can delete keys
     
  4. Key policy: Remove kms:ScheduleKeyDeletion from all users
     (require specific key-admin role assumed with MFA)
     
  5. Multi-region keys: Replica in another region provides additional safety
     (primary deleted? Replica can become primary)
     
  6. AWS Backup: Backup encrypted data to separate key
     (don't rely on single key for all critical data)
```

### Q3: How to implement field-level encryption for PII in a multi-tenant SaaS?
**Answer:**
```
Requirement: Each tenant's PII encrypted with tenant-specific key

Architecture:
  Per-tenant KMS key:
    CMK: tenant-{tenant-id}-pii-key (one per tenant)
    Alias: alias/tenant/acme/pii-key
    
  Encryption (write path):
    Application receives PII (email, SSN, phone)
    → GenerateDataKey(KeyId=tenant's CMK, EncryptionContext={"tenant": "acme"})
    → Encrypt PII fields with data key (client-side)
    → Store: encrypted_email, encrypted_ssn + encrypted_data_key
    → Non-PII fields stored in plaintext (name, preferences)
    
  Decryption (read path):
    Application reads record
    → Decrypt(EncryptedDataKey, EncryptionContext={"tenant": "acme"})
    → Decrypt PII fields with plaintext data key
    → Return to authorized user
    
  Benefits:
    - Tenant isolation: Tenant A's key can't decrypt Tenant B's data
    - Key deletion = crypto-shredding (delete key → all PII irrecoverable)
    - Audit: CloudTrail shows which service decrypted which tenant's data
    - Compliance: GDPR "right to erasure" → delete tenant's KMS key
    
  DynamoDB implementation:
    - DynamoDB Client-Side Encryption (AWS Database Encryption SDK)
    - Encrypts specific attributes (not whole item)
    - Stores encrypted material + encryption context in item
    - Search: Can't query encrypted fields → store searchable hash alongside
```

### Q4: Application needs secrets but runs on-premises. How to integrate with AWS secrets?
**Answer:**
```
Options:

1. Direct API call (simplest):
   - On-prem app → HTTPS → AWS Secrets Manager API
   - Auth: IAM user access keys (rotate regularly) OR
   - Auth: IAM Roles Anywhere (X.509 certificate → temporary credentials)
   - Cache locally with TTL (reduce API calls + latency)
   
2. IAM Roles Anywhere (recommended):
   - On-prem server has X.509 certificate (from your PKI/CA)
   - Register trust anchor in AWS (your CA cert)
   - Application exchanges certificate for temporary IAM credentials
   - Use credentials to call Secrets Manager / SSM
   - Benefits: No long-lived access keys, certificate-based identity
   
3. Secrets bridge pattern:
   - Lambda (scheduled) → reads secrets → pushes to on-prem vault
   - Or: EventBridge on secret change → Lambda → update on-prem
   - Use case: On-prem can't reach AWS (air-gapped, restricted network)
   
4. Hybrid with HashiCorp Vault:
   - Vault runs on-prem (for on-prem apps)
   - Vault AWS secrets engine: Generates dynamic AWS credentials
   - Vault sync: Some secrets synced from AWS Secrets Manager
   - Both: Use Vault for unified interface across hybrid
   
5. Systems Manager Hybrid:
   - SSM Agent on on-prem servers (registered as managed instances)
   - Access Parameter Store via SSM agent
   - Get parameters and secrets same as EC2 instances
```

### Q5: How to achieve encryption at rest for every service in your stack?
**Answer:**
```
Strategy: Account-level defaults + enforcement via policies

Implementation:

  Account-wide defaults:
    - EBS: Default encryption enabled (account setting) → all new volumes encrypted
    - S3: Bucket default encryption (SSE-KMS) + bucket policy denying unencrypted PutObject
    - RDS: Require encryption at creation (no way to encrypt existing DB without recreate)
    - DynamoDB: Encrypted by default (AWS owned key, upgrade to CMK for audit)

  Enforcement (preventive):
    SCP: Deny launching resources without encryption
    {
      "Effect": "Deny",
      "Action": "rds:CreateDBInstance",
      "Resource": "*",
      "Condition": { "Bool": { "rds:StorageEncrypted": "false" } }
    }
    
    Config Rules:
      - encrypted-volumes (EBS)
      - rds-storage-encrypted
      - s3-bucket-server-side-encryption-enabled
      - dynamodb-table-encrypted-kms
      - sqs-queue-encrypted
      
  Detective:
    Config Rules → Non-compliant → SNS alert → auto-remediation (SSM)
    
  Key management:
    - One CMK per service per environment: prod-rds-key, prod-s3-key, prod-ebs-key
    - Separate key admins from key users (separation of duties)
    - All keys auto-rotate yearly
    - CloudTrail: Audit all kms:Decrypt calls
    
  Gotchas:
    - RDS: Can't encrypt existing unencrypted DB → snapshot → copy with encryption → restore
    - EBS: Can't encrypt existing volume → snapshot → copy with encryption → create from snapshot
    - S3: Existing objects not retroactively encrypted → S3 Batch Operations (re-PUT with encryption)
    - Cross-region: Need CMK in each region (or multi-region key)
```

