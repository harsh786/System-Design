# Amazon S3 & Storage Services - Complete Guide

---

## 1. S3 Overview
- **What:** Object storage service. Unlimited storage, 0 bytes to 5 TB per object
- **Durability:** 99.999999999% (11 nines) - designed to sustain loss of 2 facilities simultaneously
- **Availability:** 99.99% (standard), varies by storage class
- **Structure:** Buckets (globally unique name) → Objects (key-value, key = full path)
- **Not a filesystem:** Flat structure, "/" in key name is just convention
- **Max object size:** 5 TB (multi-part upload required for > 5 GB, recommended for > 100 MB)

---

## 2. S3 Storage Classes

| Class | Availability | Min Duration | Retrieval Fee | Use Case |
|-------|-------------|--------------|---------------|----------|
| S3 Standard | 99.99% | None | None | Frequently accessed data |
| S3 Intelligent-Tiering | 99.9% | 30 days | None | Unknown/changing access patterns |
| S3 Standard-IA | 99.9% | 30 days | Per GB | Infrequent but rapid access |
| S3 One Zone-IA | 99.5% | 30 days | Per GB | Non-critical, recreatable data |
| S3 Glacier Instant | 99.9% | 90 days | Per GB | Archive with ms retrieval |
| S3 Glacier Flexible | 99.99% | 90 days | Per GB + request | Archive, minutes-hours retrieval |
| S3 Glacier Deep Archive | 99.99% | 180 days | Per GB + request | Long-term archive, 12-48hr retrieval |

### Intelligent-Tiering Tiers (automatic)
- Frequent Access (default)
- Infrequent Access (after 30 days no access)
- Archive Instant Access (after 90 days)
- Archive Access (optional, after 90-730 days)
- Deep Archive Access (optional, after 180-730 days)

### Cost Comparison (us-east-1, per GB/month)
| Class | Storage | Retrieval |
|-------|---------|-----------|
| Standard | $0.023 | Free |
| Standard-IA | $0.0125 | $0.01/GB |
| One Zone-IA | $0.01 | $0.01/GB |
| Glacier Instant | $0.004 | $0.03/GB |
| Glacier Flexible | $0.0036 | $0.01-$0.03/GB |
| Deep Archive | $0.00099 | $0.02-$0.05/GB |

---

## 3. S3 Lifecycle Policies
```json
{
  "Rules": [
    {
      "ID": "MoveToIA",
      "Filter": { "Prefix": "logs/" },
      "Transitions": [
        { "Days": 30, "StorageClass": "STANDARD_IA" },
        { "Days": 90, "StorageClass": "GLACIER" },
        { "Days": 365, "StorageClass": "DEEP_ARCHIVE" }
      ],
      "Expiration": { "Days": 730 },
      "NoncurrentVersionTransitions": [
        { "NoncurrentDays": 30, "StorageClass": "GLACIER" }
      ],
      "NoncurrentVersionExpiration": { "NoncurrentDays": 90 }
    }
  ]
}
```
- Transition: Move between storage classes
- Expiration: Delete objects after days
- Noncurrent versions: Handle old versions separately (with versioning)
- Abort incomplete multipart uploads: Clean up after X days

---

## 4. S3 Versioning
- **What:** Keep all versions of an object (every PUT/DELETE creates new version)
- **States:** Unversioned (default), Enabled, Suspended
- **Delete:** Adds "delete marker" (soft delete). Previous versions still exist
- **Permanent delete:** Specify version ID in delete request
- **Use case:** Data protection, accidental deletion recovery, audit trail
- **Cost:** Each version stored = additional storage cost
- **MFA Delete:** Require MFA for permanent deletion (root account only can enable)

---

## 5. S3 Replication
- **Cross-Region Replication (CRR):** Replicate to different region (compliance, lower latency)
- **Same-Region Replication (SRR):** Replicate within same region (log aggregation, live replication)
- **Requirements:** Source and destination must have versioning enabled
- **Scope:** Entire bucket, prefix, or tag-based filtering
- **What's replicated:** New objects after enabling, same storage class (or different), same owner (or different account)
- **NOT replicated:** Existing objects (use S3 Batch Replication), delete markers (optional), SSE-C encrypted objects
- **Replication Time Control (RTC):** Guarantees 99.99% replicated within 15 minutes (SLA)

---

## 6. S3 Security

### Access Control
- **Bucket Policy (resource-based):** JSON policy on bucket (most common). Public access, cross-account, VPC endpoint restrictions
- **IAM Policy (identity-based):** Attached to IAM user/role. Controls what identities can do
- **ACL (legacy):** Object-level or bucket-level. AWS recommends disabling (Bucket Owner Enforced)
- **Block Public Access:** Account-level or bucket-level setting (always enable in production)

### Encryption
| Type | Key Management | When to Use |
|------|---------------|-------------|
| SSE-S3 (default) | AWS manages everything | Default, no key management needed |
| SSE-KMS | You manage KMS key, audit trail in CloudTrail | Compliance, audit, fine-grained key control |
| SSE-C | You provide key in every request | You want full key control, key never stored by AWS |
| Client-side | You encrypt before upload | Maximum security, AWS never sees plaintext |

### Other Security Features
- **Object Lock:** WORM (Write Once Read Many). Governance mode (admin can override), Compliance mode (nobody can delete, including root)
- **Legal Hold:** Like Object Lock but no retention period (hold until explicitly removed)
- **Access Points:** Simplified access management for shared datasets (per-team access point with own policy)
- **S3 Access Grants:** Map identities (AD groups, SAML) to S3 prefixes (no IAM policy per user)
- **VPC Endpoint (Gateway):** Access S3 without internet (free, just route table entry)
- **Pre-signed URLs:** Temporary access to private objects (configurable expiry)

---

## 7. S3 Performance
- **Baseline:** 3,500 PUT/COPY/POST/DELETE + 5,500 GET/HEAD requests per second per prefix
- **Scaling:** Automatically scales. Spread across prefixes for higher throughput
- **Multi-part upload:** Required for > 5GB, recommended for > 100MB. Parallel upload of parts
- **S3 Transfer Acceleration:** Uses CloudFront edge locations for faster upload (global users → edge → S3)
- **Byte-Range Fetches:** Download specific byte range (parallel downloads, resume)
- **S3 Select / Glacier Select:** SQL query on CSV/JSON/Parquet without downloading full object
- **Batch Operations:** Perform actions on billions of objects (copy, tag, restore, invoke Lambda)

---

## 8. S3 Event Notifications
- **Events:** s3:ObjectCreated, s3:ObjectRemoved, s3:ObjectRestore, s3:Replication
- **Destinations:** SQS, SNS, Lambda, EventBridge (recommended - richest filtering)
- **Use cases:** Thumbnail generation, data pipeline trigger, log processing, compliance alerts
- **EventBridge:** Advanced filtering (object size, prefix, suffix, metadata), multiple targets, archive/replay

---

## 9. S3 Advanced Features
- **S3 Object Lambda:** Transform data on retrieval (redact PII, resize images, decompress)
- **S3 Inventory:** CSV/ORC/Parquet report of all objects (weekly/daily). Use for: audit, lifecycle, cost analysis
- **S3 Analytics:** Storage class analysis (recommend IA transition based on access patterns)
- **S3 Lens:** Organization-wide storage visibility and recommendations
- **Requester Pays:** Requester pays data transfer costs (data sharing use case)
- **S3 on Outposts:** S3 API on AWS Outposts (on-premises)
- **Mountpoint for S3:** Mount S3 bucket as local filesystem (high-throughput read workloads)

---

## 10. Other AWS Storage Services

### EFS (Elastic File System)
- **NFS v4.1** managed file system
- Multi-AZ, auto-scaling, shared across instances/containers/Lambda
- Performance modes: General Purpose (latency-sensitive), Max I/O (high throughput)
- Throughput modes: Bursting, Provisioned, Elastic
- Storage classes: Standard, Infrequent Access (lifecycle policies)
- **Use case:** Shared storage for web content, CMS, dev tools, ML training data

### FSx
- **FSx for Windows File Server:** SMB protocol, Active Directory integration, Windows workloads
- **FSx for Lustre:** High-performance parallel filesystem (ML training, HPC, video rendering). Integrates with S3
- **FSx for NetApp ONTAP:** Enterprise NAS features, multi-protocol (NFS, SMB, iSCSI)
- **FSx for OpenZFS:** Linux workloads migrating from on-prem ZFS

### Storage Gateway
- Hybrid cloud storage (on-prem ↔ AWS)
- **File Gateway:** NFS/SMB → S3 (local cache)
- **Volume Gateway:** iSCSI block storage → EBS snapshots in S3
- **Tape Gateway:** Virtual tape library → S3 Glacier (backup migration)

### AWS Backup
- Centralized backup across services (EC2, EBS, RDS, DynamoDB, EFS, FSx, S3)
- Backup plans, retention policies, cross-region/cross-account copy
- Vault lock: WORM for compliance (immutable backups)

---

## 11. Scenario-Based Interview Questions

### Q1: Design cost-effective storage for 500TB of logs with varying access patterns
**Answer:**
- Hot (0-7 days): S3 Standard. Queried frequently for debugging
- Warm (7-30 days): S3 Standard-IA. Occasional access for investigations
- Cold (30-90 days): S3 Glacier Instant Retrieval. Rare access, need ms retrieval
- Archive (90-365 days): S3 Glacier Flexible. Very rare, hours retrieval OK
- Delete after 365 days (or Deep Archive for compliance)
- Lifecycle policy automates all transitions. Cost: ~$0.004/GB/month average vs $0.023 all Standard

### Q2: S3 bucket accidentally made public. Incident response?
**Answer:**
1. Immediate: Enable "Block Public Access" at bucket level (instant fix)
2. Audit: Check CloudTrail for who changed policy and when
3. Impact: Use S3 server access logs or CloudTrail data events to see who accessed
4. Prevention: SCP blocking s3:PutBucketPolicy with public access, Config Rule alert, Macie for sensitive data detection
5. Monitoring: Enable GuardDuty S3 protection, Macie for PII scanning

### Q3: Migrate 100TB from on-prem to S3 with minimal downtime
**Answer:**
- **Network calculation:** 100TB over 1Gbps = ~9 days. Over 10Gbps = ~1 day
- **Options:**
  - AWS DataSync: Over Direct Connect/VPN. Supports incremental sync
  - AWS Snowball Edge: Physical device shipped (80TB per device). 2 devices + ship = 1-2 weeks
  - S3 Transfer Acceleration: If using internet, speeds up via CloudFront edges
- **Strategy:** Snowball for initial bulk + DataSync for incremental changes + final cutover

### Q4: Design S3-based data lake architecture
**Answer:**
```
Raw Zone (S3 bucket):
  s3://data-lake-raw/ → original data, immutable, all formats
  Lifecycle: Glacier after 90 days

Processed Zone (S3 bucket):  
  s3://data-lake-processed/ → cleaned, Parquet/ORC format, partitioned
  Partitioning: year=2024/month=01/day=15/

Curated Zone (S3 bucket):
  s3://data-lake-curated/ → business-ready, aggregated, documented

Query: Athena (ad-hoc SQL), Redshift Spectrum (BI tools), EMR (heavy processing)
Catalog: Glue Data Catalog (central schema registry)
Governance: Lake Formation (fine-grained permissions)
Processing: Glue ETL jobs (Spark-based transformations)
```

### Q5: S3 performance optimization for millions of small files
**Answer:**
- Use random prefixes (hash-based) to distribute across partitions
- Modern S3 (2018+): 3,500 PUT + 5,500 GET per prefix → use multiple prefixes
- Batch small files into larger files (parquet, zip) for fewer requests
- Enable S3 Transfer Acceleration for global uploads
- Use multipart upload + parallel threads for large files
- For reads: CloudFront in front of S3 (cache small files at edge)

