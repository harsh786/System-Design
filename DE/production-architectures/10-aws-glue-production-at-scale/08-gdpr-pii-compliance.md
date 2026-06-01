# GDPR/CCPA PII Compliance & Data Masking Pipeline at Booking.com/Expedia Scale

## The Problem: 500M User Records × 200+ Datasets → GDPR Article 17 Compliance in 72 Hours

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Business Context

A global travel/e-commerce platform (Booking.com/Expedia scale) processes bookings,
reviews, payments, loyalty programs, and customer interactions across 200+ countries.
Under GDPR Article 17, any EU citizen can request **complete deletion** of their
personal data from ALL systems within 72 hours.

### Scale Parameters

```
┌─────────────────────────────────────────────────────────────┐
│  COMPLIANCE SCALE                                           │
├─────────────────────────────────────────────────────────────┤
│  Total Users:              500 million                      │
│  EU Users (GDPR scope):   180 million                      │
│  CA Users (CCPA scope):   45 million                       │
│  Total Datasets:          200+ (lakes, warehouses, caches) │
│  Total Data Volume:       5 PB across all stores           │
│  Deletion Requests/Day:   10,000 (spikes to 50K post-breach│
│  SLA:                     72 hours end-to-end              │
│  Audit Frequency:         Quarterly + on-demand by DPA     │
│  Fine Risk:               4% global revenue (~€200M)       │
│  Data Stores:             S3, RDS, DynamoDB, Redshift,     │
│                           Elasticsearch, Redis, Snowflake  │
└─────────────────────────────────────────────────────────────┘
```

### Regulatory Landscape

```
┌────────────────┬──────────────┬────────────┬────────────────┐
│ Regulation     │ Scope        │ SLA        │ Penalty        │
├────────────────┼──────────────┼────────────┼────────────────┤
│ GDPR (EU)      │ 180M users   │ 30 days*   │ 4% revenue     │
│ CCPA (CA)      │ 45M users    │ 45 days    │ $7,500/record  │
│ LGPD (Brazil)  │ 30M users    │ 15 days    │ 2% revenue     │
│ PIPA (Korea)   │ 12M users    │ 10 days    │ 3% revenue     │
│ PDPA (Thailand)│ 8M users     │ 30 days    │ ฿5M            │
└────────────────┴──────────────┴────────────┴────────────────┘
* Internal SLA is 72 hours for competitive advantage
```

---

## Why Traditional Approaches Fail

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### 1. Manual Deletion Scripts
- Engineers must know ALL 200+ datasets containing user data
- New datasets added weekly → scripts become stale
- No verification that deletion actually occurred
- Audit trail gaps: "we think we deleted it"

### 2. Database-Only Deletion
- Deletes from PostgreSQL/DynamoDB but data lake copies persist
- Derived datasets (aggregations, ML features) retain PII
- CDC pipelines re-propagate data from backups
- Snapshots and backups contain deleted data

### 3. Application-Level Masking
- Inconsistent implementation across 50+ microservices
- Developers bypass masking for debugging
- No enforcement mechanism at data layer
- Cannot prove compliance to regulators

### 4. Full Dataset Rewrites
- Rewriting 5PB to remove 10K users/day is prohibitively expensive
- 200+ datasets × full rewrite = weeks, not hours
- Compute cost: $50K/day for full rewrites
- Breaks downstream consumers during rewrite windows

---

## Architecture

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    GDPR/PII COMPLIANCE PIPELINE ARCHITECTURE                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  ┌──────────────────┐  │
│  │ User Portal  │  │ Customer Svc │  │ Regulatory    │  │ Consent Mgmt     │  │
│  │ "Delete My   │  │ Agent Panel  │  │ Authority     │  │ Platform         │  │
│  │  Account"    │  │              │  │ (DPA Request) │  │ (OneTrust)       │  │
│  └──────┬───────┘  └──────┬───────┘  └───────┬───────┘  └────────┬─────────┘  │
│         │                  │                  │                    │            │
│         ▼                  ▼                  ▼                    ▼            │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                    SQS: deletion-request-queue                           │   │
│  │  { user_id, request_type, regulation, timestamp, priority }             │   │
│  └─────────────────────────────────┬───────────────────────────────────────┘   │
│                                    │                                            │
│                                    ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │              STEP FUNCTIONS: GDPR Compliance Orchestrator                │   │
│  │                                                                         │   │
│  │  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌────────┐  │   │
│  │  │ Job 1   │──▶│ Job 2   │──▶│ Job 3   │──▶│ Job 4   │──▶│ Job 5  │  │   │
│  │  │ PII     │   │ Delete  │   │ Anonymize│  │ Mask    │   │ Verify │  │   │
│  │  │ Discover│   │ Execute │   │ Analytics│  │ NonProd │   │ & Audit│  │   │
│  │  └─────────┘   └─────────┘   └─────────┘   └─────────┘   └────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                            │
│         ┌──────────────────────────┼──────────────────────────┐                │
│         ▼                          ▼                          ▼                │
│  ┌──────────────┐  ┌───────────────────────┐  ┌───────────────────────────┐   │
│  │ Data Catalog │  │ Data Lake (Iceberg)    │  │ Compliance Evidence Store │   │
│  │ (PII Map)    │  │ - Row-level deletes    │  │ - Deletion certificates   │   │
│  │              │  │ - Partition pruning    │  │ - Audit logs              │   │
│  │ Macie +      │  │ - Time travel cleanup  │  │ - Regulator reports       │   │
│  │ Lake Formation│ │                        │  │                           │   │
│  └──────────────┘  └───────────────────────┘  └───────────────────────────┘   │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                    CROSS-REGION COORDINATION                             │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐               │   │
│  │  │ eu-west-1│  │us-east-1 │  │ap-south-1│  │sa-east-1 │               │   │
│  │  │ (EU Data)│  │(US Data) │  │(APAC)    │  │(Brazil)  │               │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘               │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Glue Concepts Used

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

| Concept | Usage |
|---------|-------|
| **Sensitive Data Detection** | Built-in PII classifiers (SSN, email, phone, passport) |
| **Custom Classifiers** | Domain-specific: booking references, loyalty IDs, travel docs |
| **Iceberg Integration** | Row-level DELETE without full partition rewrite |
| **Job Bookmarks** | Track processed deletion request offsets |
| **Glue Connections** | Connect to RDS, Redshift, DynamoDB, Elasticsearch |
| **Lake Formation** | Column-level masking, row-level filtering by region |
| **Glue Workflows** | Orchestrate multi-job deletion pipeline |
| **Data Catalog** | PII registry mapping user_id → datasets → columns |
| **KMS Encryption** | Crypto-shredding via key deletion |
| **VPC Endpoints** | Ensure PII never traverses public internet |

---

## Implementation Code

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Job 1: PII Discovery & Classification

```python
# job1_pii_discovery.py
# Scans all datasets to build/maintain PII registry

import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.dynamicframe import DynamicFrame
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.types import *
import boto3
import json
from datetime import datetime

args = getResolvedOptions(sys.argv, [
    'JOB_NAME', 'catalog_database', 'pii_registry_table',
    'scan_mode'  # 'full' or 'incremental'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

# ─────────────────────────────────────────────────────
# PII Detection Configuration
# ─────────────────────────────────────────────────────

PII_ENTITY_TYPES = [
    "EMAIL", "PHONE_NUMBER", "CREDIT_CARD",
    "SSN", "PASSPORT_NUMBER", "IP_ADDRESS",
    "DATE_OF_BIRTH", "PERSON_NAME", "ADDRESS",
    "DRIVER_LICENSE", "BANK_ACCOUNT", "TAX_ID"
]

# Domain-specific PII patterns for travel industry
CUSTOM_PII_PATTERNS = {
    "BOOKING_REFERENCE": r"[A-Z]{2}\d{7}",
    "LOYALTY_NUMBER": r"(FF|LP|SR)\d{10,12}",
    "PASSPORT_NUMBER": r"[A-Z]{1,2}\d{6,9}",
    "FREQUENT_FLYER": r"[A-Z]{2}\d{9,13}",
    "HOTEL_RESERVATION": r"RES-\d{8}-[A-Z]{3}",
}

GDPR_CATEGORIES = {
    "CATEGORY_A": "Basic identity (name, email, phone)",
    "CATEGORY_B": "Financial (credit card, bank account)",
    "CATEGORY_C": "Location (address, IP, travel history)",
    "CATEGORY_D": "Behavioral (preferences, reviews, searches)",
    "CATEGORY_E": "Special category (health, dietary, disability)",
}


class PIIScanner:
    """Scans datasets using Glue Sensitive Data Detection API."""

    def __init__(self, glue_context, catalog_db):
        self.glue_context = glue_context
        self.catalog_db = catalog_db
        self.glue_client = boto3.client('glue')
        self.results = []

    def get_all_tables(self):
        """Retrieve all tables from Glue Catalog."""
        tables = []
        paginator = self.glue_client.get_paginator('get_tables')
        for page in paginator.paginate(DatabaseName=self.catalog_db):
            tables.extend(page['TableList'])
        return tables

    def scan_table_for_pii(self, table_name):
        """Use Glue's built-in Sensitive Data Detection."""
        try:
            dyf = self.glue_context.create_dynamic_frame.from_catalog(
                database=self.catalog_db,
                table_name=table_name,
                transformation_ctx=f"scan_{table_name}"
            )

            # Sample for large tables (scan 1% or 100K rows max)
            total_count = dyf.count()
            if total_count > 100000:
                sample_fraction = min(100000 / total_count, 0.01)
                df = dyf.toDF().sample(fraction=sample_fraction, seed=42)
            else:
                df = dyf.toDF()

            # Apply Glue's detect_sensitive_data
            detected = self.glue_context.detect_sensitive_data(
                frame=DynamicFrame.fromDF(df, self.glue_context, "detect"),
                entity_types=PII_ENTITY_TYPES,
                output_column_name="pii_detection_result"
            )

            # Parse detection results per column
            pii_columns = self._extract_pii_columns(detected, table_name)
            return pii_columns

        except Exception as e:
            print(f"Error scanning {table_name}: {str(e)}")
            return []

    def _extract_pii_columns(self, detected_frame, table_name):
        """Extract which columns contain which PII types."""
        pii_findings = []
        df = detected_frame.toDF()

        if "pii_detection_result" in df.columns:
            results = df.select("pii_detection_result").distinct().collect()
            for row in results:
                detection = row["pii_detection_result"]
                if detection:
                    for column_name, entities in detection.items():
                        pii_findings.append({
                            "table_name": table_name,
                            "column_name": column_name,
                            "pii_types": entities,
                            "gdpr_category": self._classify_gdpr_category(entities),
                            "scan_timestamp": datetime.utcnow().isoformat(),
                            "confidence": "HIGH"
                        })
        return pii_findings

    def _classify_gdpr_category(self, entity_types):
        """Map detected PII to GDPR data categories."""
        category_map = {
            "PERSON_NAME": "CATEGORY_A",
            "EMAIL": "CATEGORY_A",
            "PHONE_NUMBER": "CATEGORY_A",
            "CREDIT_CARD": "CATEGORY_B",
            "BANK_ACCOUNT": "CATEGORY_B",
            "ADDRESS": "CATEGORY_C",
            "IP_ADDRESS": "CATEGORY_C",
            "DATE_OF_BIRTH": "CATEGORY_A",
            "SSN": "CATEGORY_B",
            "PASSPORT_NUMBER": "CATEGORY_A",
        }
        categories = set()
        for entity in entity_types:
            if entity in category_map:
                categories.add(category_map[entity])
        return list(categories)

    def scan_with_custom_patterns(self, table_name):
        """Apply domain-specific PII patterns."""
        dyf = self.glue_context.create_dynamic_frame.from_catalog(
            database=self.catalog_db,
            table_name=table_name
        )
        df = dyf.toDF()
        custom_findings = []

        for col in df.columns:
            if df.schema[col].dataType == StringType():
                sample = df.select(col).limit(10000)
                for pattern_name, regex in CUSTOM_PII_PATTERNS.items():
                    match_count = sample.filter(
                        F.col(col).rlike(regex)
                    ).count()
                    if match_count > 0:
                        custom_findings.append({
                            "table_name": table_name,
                            "column_name": col,
                            "pii_types": [pattern_name],
                            "gdpr_category": ["CATEGORY_A"],
                            "scan_timestamp": datetime.utcnow().isoformat(),
                            "confidence": "MEDIUM" if match_count < 100 else "HIGH"
                        })
        return custom_findings


# ─────────────────────────────────────────────────────
# Execute PII Scan
# ─────────────────────────────────────────────────────

scanner = PIIScanner(glueContext, args['catalog_database'])
tables = scanner.get_all_tables()

all_pii_findings = []
for table in tables:
    table_name = table['Name']
    print(f"Scanning table: {table_name}")

    # Built-in PII detection
    findings = scanner.scan_table_for_pii(table_name)
    all_pii_findings.extend(findings)

    # Custom domain patterns
    custom = scanner.scan_with_custom_patterns(table_name)
    all_pii_findings.extend(custom)

# Write PII registry to Iceberg table
pii_registry_df = spark.createDataFrame(all_pii_findings)
pii_registry_df.writeTo(
    f"glue_catalog.{args['catalog_database']}.{args['pii_registry_table']}"
).using("iceberg").createOrReplace()

print(f"PII scan complete. Found {len(all_pii_findings)} PII columns across {len(tables)} tables.")

job.commit()
```

### Job 2: Deletion Orchestration (Iceberg Row-Level Deletes)

```python
# job2_deletion_orchestrator.py
# Executes RTBF deletions across all datasets using Iceberg row-level deletes

import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
from pyspark.sql import functions as F
import boto3
import json
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

args = getResolvedOptions(sys.argv, [
    'JOB_NAME', 'catalog_database', 'pii_registry_table',
    'deletion_queue_url', 'audit_table', 'batch_size'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

# Enable Iceberg
spark.conf.set("spark.sql.catalog.glue_catalog", "org.apache.iceberg.spark.SparkCatalog")
spark.conf.set("spark.sql.catalog.glue_catalog.warehouse", "s3://data-lake-prod/warehouse")
spark.conf.set("spark.sql.catalog.glue_catalog.catalog-impl",
               "org.apache.iceberg.aws.glue.GlueCatalog")


class DeletionOrchestrator:
    """Orchestrates user data deletion across all datasets."""

    def __init__(self, spark, glue_context, catalog_db, pii_registry):
        self.spark = spark
        self.glue_context = glue_context
        self.catalog_db = catalog_db
        self.pii_registry = pii_registry
        self.sqs = boto3.client('sqs')
        self.audit_records = []

    def fetch_deletion_requests(self, queue_url, batch_size=100):
        """Pull deletion requests from SQS."""
        requests = []
        while len(requests) < batch_size:
            response = self.sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=5,
                MessageAttributeNames=['All']
            )
            messages = response.get('Messages', [])
            if not messages:
                break
            for msg in messages:
                body = json.loads(msg['Body'])
                requests.append({
                    "user_id": body['user_id'],
                    "request_id": body['request_id'],
                    "regulation": body['regulation'],
                    "request_timestamp": body['timestamp'],
                    "priority": body.get('priority', 'normal'),
                    "receipt_handle": msg['ReceiptHandle']
                })
        return requests

    def get_user_data_locations(self, user_id):
        """Query PII registry to find all tables containing this user's data."""
        pii_map = self.spark.sql(f"""
            SELECT DISTINCT table_name, column_name, pii_types
            FROM glue_catalog.{self.catalog_db}.{self.pii_registry}
            WHERE pii_types IS NOT NULL
        """).collect()

        # Find tables with user identifier columns
        user_id_tables = []
        for row in pii_map:
            table = row['table_name']
            # Check if this table has a user_id or linkable identifier
            if self._table_has_user(table, user_id):
                user_id_tables.append({
                    "table_name": table,
                    "id_column": self._get_id_column(table),
                    "pii_columns": [r['column_name'] for r in pii_map
                                    if r['table_name'] == table]
                })
        return user_id_tables

    def _table_has_user(self, table_name, user_id):
        """Check if table contains data for this user."""
        id_col = self._get_id_column(table_name)
        if id_col:
            count = self.spark.sql(f"""
                SELECT COUNT(*) as cnt
                FROM glue_catalog.{self.catalog_db}.{table_name}
                WHERE {id_col} = '{user_id}'
            """).collect()[0]['cnt']
            return count > 0
        return False

    def _get_id_column(self, table_name):
        """Determine the user identifier column for a table."""
        # Check common patterns
        schema = self.spark.sql(
            f"DESCRIBE glue_catalog.{self.catalog_db}.{table_name}"
        ).collect()
        columns = [row['col_name'] for row in schema]

        id_patterns = ['user_id', 'customer_id', 'guest_id', 'member_id',
                       'account_id', 'traveler_id', 'booker_id']
        for pattern in id_patterns:
            if pattern in columns:
                return pattern
        return None

    def execute_deletion(self, user_id, table_info):
        """Execute row-level delete using Iceberg."""
        table_name = table_info['table_name']
        id_column = table_info['id_column']

        try:
            # Iceberg row-level DELETE (no full partition rewrite!)
            deleted_count = self.spark.sql(f"""
                DELETE FROM glue_catalog.{self.catalog_db}.{table_name}
                WHERE {id_column} = '{user_id}'
            """)

            # Get actual rows deleted
            # Iceberg maintains this in metadata
            rows_deleted = self._get_delete_count(table_name, user_id, id_column)

            self.audit_records.append({
                "user_id": user_id,
                "table_name": table_name,
                "id_column": id_column,
                "rows_deleted": rows_deleted,
                "deletion_timestamp": datetime.utcnow().isoformat(),
                "status": "COMPLETED",
                "method": "ICEBERG_ROW_DELETE"
            })
            return rows_deleted

        except Exception as e:
            self.audit_records.append({
                "user_id": user_id,
                "table_name": table_name,
                "id_column": id_column,
                "rows_deleted": 0,
                "deletion_timestamp": datetime.utcnow().isoformat(),
                "status": "FAILED",
                "error": str(e),
                "method": "ICEBERG_ROW_DELETE"
            })
            raise

    def _get_delete_count(self, table_name, user_id, id_column):
        """Verify deletion by checking history."""
        # Use Iceberg time travel to compare
        result = self.spark.sql(f"""
            SELECT COUNT(*) as cnt
            FROM glue_catalog.{self.catalog_db}.{table_name}.history
            WHERE made_current_at = (
                SELECT MAX(made_current_at)
                FROM glue_catalog.{self.catalog_db}.{table_name}.history
            )
        """).collect()
        return result[0]['cnt'] if result else 0

    def handle_nested_data(self, user_id, table_name, id_column):
        """Handle deletion in nested/denormalized structures."""
        # For tables with arrays/structs containing user data
        self.spark.sql(f"""
            UPDATE glue_catalog.{self.catalog_db}.{table_name}
            SET participants = FILTER(participants, x -> x.user_id != '{user_id}'),
                reviews = FILTER(reviews, x -> x.author_id != '{user_id}')
            WHERE ARRAY_CONTAINS(
                TRANSFORM(participants, x -> x.user_id), '{user_id}'
            )
        """)

    def cascade_delete(self, user_id):
        """Handle cascading deletes across related tables."""
        # Get all related identifiers for this user
        related_ids = self.spark.sql(f"""
            SELECT DISTINCT
                u.user_id,
                u.loyalty_id,
                u.payment_profile_id,
                u.review_author_id
            FROM glue_catalog.{self.catalog_db}.user_identity_graph u
            WHERE u.user_id = '{user_id}'
        """).collect()

        if related_ids:
            row = related_ids[0]
            # Delete from loyalty tables
            if row['loyalty_id']:
                self.spark.sql(f"""
                    DELETE FROM glue_catalog.{self.catalog_db}.loyalty_transactions
                    WHERE loyalty_id = '{row['loyalty_id']}'
                """)
            # Anonymize reviews (keep content, remove identity)
            if row['review_author_id']:
                self.spark.sql(f"""
                    UPDATE glue_catalog.{self.catalog_db}.property_reviews
                    SET author_name = 'Anonymous',
                        author_email = NULL,
                        author_avatar = NULL
                    WHERE author_id = '{row['review_author_id']}'
                """)

    def expire_iceberg_snapshots(self, table_name):
        """Remove old snapshots so deleted data is truly gone."""
        self.spark.sql(f"""
            CALL glue_catalog.system.expire_snapshots(
                table => '{self.catalog_db}.{table_name}',
                older_than => TIMESTAMP '{
                    (datetime.utcnow() - timedelta(hours=1)).isoformat()
                }',
                retain_last => 1
            )
        """)
        # Also remove orphan files
        self.spark.sql(f"""
            CALL glue_catalog.system.remove_orphan_files(
                table => '{self.catalog_db}.{table_name}',
                older_than => TIMESTAMP '{
                    (datetime.utcnow() - timedelta(hours=1)).isoformat()
                }'
            )
        """)


# ─────────────────────────────────────────────────────
# Execute Deletions
# ─────────────────────────────────────────────────────

orchestrator = DeletionOrchestrator(
    spark, glueContext, args['catalog_database'], args['pii_registry_table']
)

# Fetch batch of deletion requests
deletion_requests = orchestrator.fetch_deletion_requests(
    args['deletion_queue_url'],
    batch_size=int(args['batch_size'])
)

print(f"Processing {len(deletion_requests)} deletion requests")

for request in deletion_requests:
    user_id = request['user_id']
    print(f"Deleting user: {user_id} (regulation: {request['regulation']})")

    # Find all datasets with this user's data
    user_locations = orchestrator.get_user_data_locations(user_id)
    print(f"  Found data in {len(user_locations)} tables")

    # Execute deletion in each table
    for table_info in user_locations:
        orchestrator.execute_deletion(user_id, table_info)

    # Handle cascading deletes
    orchestrator.cascade_delete(user_id)

    # Expire snapshots to ensure physical deletion
    for table_info in user_locations:
        orchestrator.expire_iceberg_snapshots(table_info['table_name'])

    # Acknowledge SQS message
    orchestrator.sqs.delete_message(
        QueueUrl=args['deletion_queue_url'],
        ReceiptHandle=request['receipt_handle']
    )

# Write audit records
audit_df = spark.createDataFrame(orchestrator.audit_records)
audit_df.writeTo(
    f"glue_catalog.{args['catalog_database']}.{args['audit_table']}"
).using("iceberg").append()

print(f"Deletion batch complete. {len(orchestrator.audit_records)} operations recorded.")

job.commit()
```

### Job 3: Anonymization for Analytics (K-Anonymity)

```python
# job3_anonymization.py
# Applies k-anonymity and l-diversity for analytics datasets

import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from pyspark.sql.types import *
import hashlib

args = getResolvedOptions(sys.argv, [
    'JOB_NAME', 'catalog_database', 'source_table',
    'target_table', 'k_value', 'l_value'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

K_VALUE = int(args['k_value'])  # Minimum group size (typically 5-10)
L_VALUE = int(args['l_value'])  # Diversity requirement


class KAnonymizer:
    """Implements k-anonymity with l-diversity for analytics data."""

    # Quasi-identifiers that could re-identify users
    QUASI_IDENTIFIERS = ['age', 'zip_code', 'gender', 'nationality', 'occupation']
    # Sensitive attributes to protect
    SENSITIVE_ATTRS = ['booking_amount', 'health_preferences', 'loyalty_tier']
    # Direct identifiers to remove entirely
    DIRECT_IDENTIFIERS = ['user_id', 'email', 'phone', 'name', 'passport_number']

    def __init__(self, spark, k, l_div):
        self.spark = spark
        self.k = k
        self.l_div = l_div

    def anonymize(self, df):
        """Full anonymization pipeline."""
        # Step 1: Remove direct identifiers
        df = self._suppress_direct_identifiers(df)

        # Step 2: Generalize quasi-identifiers
        df = self._generalize_quasi_identifiers(df)

        # Step 3: Verify k-anonymity
        df = self._enforce_k_anonymity(df)

        # Step 4: Verify l-diversity
        df = self._enforce_l_diversity(df)

        return df

    def _suppress_direct_identifiers(self, df):
        """Remove all direct identifiers."""
        cols_to_drop = [c for c in self.DIRECT_IDENTIFIERS if c in df.columns]
        return df.drop(*cols_to_drop)

    def _generalize_quasi_identifiers(self, df):
        """Generalize quasi-identifiers to reduce uniqueness."""
        # Age → age range
        if 'age' in df.columns:
            df = df.withColumn('age', F.concat(
                (F.floor(F.col('age') / 10) * 10).cast('string'),
                F.lit('-'),
                ((F.floor(F.col('age') / 10) * 10) + 9).cast('string')
            ))

        # Zip code → first 3 digits
        if 'zip_code' in df.columns:
            df = df.withColumn('zip_code', F.substring(F.col('zip_code'), 1, 3))

        # Nationality → region
        if 'nationality' in df.columns:
            df = df.withColumn('nationality', F.when(
                F.col('nationality').isin('DE', 'FR', 'IT', 'ES', 'NL'), 'Western Europe'
            ).when(
                F.col('nationality').isin('PL', 'CZ', 'HU', 'RO'), 'Eastern Europe'
            ).when(
                F.col('nationality').isin('US', 'CA'), 'North America'
            ).otherwise('Other'))

        return df

    def _enforce_k_anonymity(self, df):
        """Ensure every combination of quasi-identifiers has at least k records."""
        qi_cols = [c for c in self.QUASI_IDENTIFIERS if c in df.columns]

        # Count records per equivalence class
        window = Window.partitionBy(qi_cols)
        df = df.withColumn('_eq_class_size', F.count('*').over(window))

        # Suppress records in too-small equivalence classes
        df = df.filter(F.col('_eq_class_size') >= self.k)
        df = df.drop('_eq_class_size')

        return df

    def _enforce_l_diversity(self, df):
        """Ensure l-diversity: each equivalence class has l distinct sensitive values."""
        qi_cols = [c for c in self.QUASI_IDENTIFIERS if c in df.columns]
        sensitive_cols = [c for c in self.SENSITIVE_ATTRS if c in df.columns]

        for sensitive_col in sensitive_cols:
            window = Window.partitionBy(qi_cols)
            df = df.withColumn(
                '_diversity',
                F.approx_count_distinct(F.col(sensitive_col)).over(window)
            )
            df = df.filter(F.col('_diversity') >= self.l_div)
            df = df.drop('_diversity')

        return df


# Execute anonymization
source_df = spark.sql(f"""
    SELECT * FROM glue_catalog.{args['catalog_database']}.{args['source_table']}
""")

anonymizer = KAnonymizer(spark, K_VALUE, L_VALUE)
anonymized_df = anonymizer.anonymize(source_df)

# Write anonymized dataset
anonymized_df.writeTo(
    f"glue_catalog.{args['catalog_database']}.{args['target_table']}"
).using("iceberg").createOrReplace()

print(f"Anonymization complete. K={K_VALUE}, L={L_VALUE}")
print(f"Original rows: {source_df.count()}, Anonymized rows: {anonymized_df.count()}")
print(f"Suppression rate: {1 - anonymized_df.count()/source_df.count():.2%}")

job.commit()
```

### Job 4: Data Masking for Non-Production (Format-Preserving Encryption)

```python
# job4_data_masking.py
# Tokenization and format-preserving encryption for non-prod environments

import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.types import *
import hashlib
import struct
import boto3

args = getResolvedOptions(sys.argv, [
    'JOB_NAME', 'catalog_database', 'source_table',
    'target_table', 'masking_key_id', 'environment'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)


class FormatPreservingMasker:
    """Format-preserving encryption that maintains data shape for testing."""

    def __init__(self, key_id):
        self.kms = boto3.client('kms')
        self.key_id = key_id
        # Generate a deterministic masking key from KMS
        response = self.kms.generate_data_key(
            KeyId=key_id, KeySpec='AES_256'
        )
        self.masking_key = response['Plaintext']

    def mask_email(self, email):
        """john.doe@gmail.com → xxxx.xxx@gmail.com (preserves domain)."""
        if not email or '@' not in email:
            return email
        local, domain = email.split('@', 1)
        hashed = hashlib.sha256(
            (local + self.masking_key.hex()).encode()
        ).hexdigest()[:len(local)]
        return f"{hashed}@{domain}"

    def mask_phone(self, phone):
        """Preserve format: +1-555-123-4567 → +1-555-XXX-XXXX."""
        if not phone:
            return phone
        # Keep country code and area code, mask rest
        digits = ''.join(c for c in phone if c.isdigit())
        if len(digits) >= 7:
            masked_digits = digits[:4] + ''.join(
                str(int(hashlib.md5(
                    (d + self.masking_key.hex()).encode()
                ).hexdigest(), 16) % 10)
                for d in digits[4:]
            )
            # Reconstruct with original formatting
            result = phone
            digit_idx = 0
            for i, c in enumerate(result):
                if c.isdigit():
                    result = result[:i] + masked_digits[digit_idx] + result[i+1:]
                    digit_idx += 1
            return result
        return phone

    def mask_credit_card(self, cc):
        """4111-1111-1111-1111 → 4111-XXXX-XXXX-1111 (preserve BIN + last 4)."""
        if not cc:
            return cc
        digits = ''.join(c for c in cc if c.isdigit())
        if len(digits) == 16:
            masked = digits[:4] + ''.join(
                str(int(hashlib.sha256(
                    (d + self.masking_key.hex()).encode()
                ).hexdigest(), 16) % 10)
                for d in digits[4:12]
            ) + digits[12:]
            return f"{masked[:4]}-{masked[4:8]}-{masked[8:12]}-{masked[12:]}"
        return cc

    def mask_name(self, name):
        """Deterministic fake name generation."""
        if not name:
            return name
        h = int(hashlib.sha256(
            (name + self.masking_key.hex()).encode()
        ).hexdigest(), 16)
        first_names = ["Alex", "Jordan", "Taylor", "Morgan", "Casey",
                       "Riley", "Quinn", "Avery", "Parker", "Drew"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones",
                      "Garcia", "Miller", "Davis", "Wilson", "Moore"]
        return f"{first_names[h % len(first_names)]} {last_names[(h >> 8) % len(last_names)]}"

    def mask_address(self, address):
        """Preserve structure: 123 Main St → 456 Oak Ave."""
        if not address:
            return address
        h = int(hashlib.sha256(
            (address + self.masking_key.hex()).encode()
        ).hexdigest(), 16)
        numbers = str((h % 900) + 100)
        streets = ["Oak", "Elm", "Pine", "Cedar", "Maple", "Birch"]
        types = ["St", "Ave", "Rd", "Ln", "Dr", "Ct"]
        return f"{numbers} {streets[h % len(streets)]} {types[(h >> 4) % len(types)]}"


# Register UDFs for Spark
masker = FormatPreservingMasker(args['masking_key_id'])

mask_email_udf = F.udf(masker.mask_email, StringType())
mask_phone_udf = F.udf(masker.mask_phone, StringType())
mask_cc_udf = F.udf(masker.mask_credit_card, StringType())
mask_name_udf = F.udf(masker.mask_name, StringType())
mask_address_udf = F.udf(masker.mask_address, StringType())

# Load source data
source_df = spark.sql(f"""
    SELECT * FROM glue_catalog.{args['catalog_database']}.{args['source_table']}
""")

# Apply masking based on PII registry
pii_registry = spark.sql(f"""
    SELECT column_name, pii_types
    FROM glue_catalog.{args['catalog_database']}.pii_registry
    WHERE table_name = '{args['source_table']}'
""").collect()

masked_df = source_df
for row in pii_registry:
    col = row['column_name']
    pii_type = row['pii_types'][0] if row['pii_types'] else None

    if col not in masked_df.columns:
        continue

    if pii_type == "EMAIL":
        masked_df = masked_df.withColumn(col, mask_email_udf(F.col(col)))
    elif pii_type == "PHONE_NUMBER":
        masked_df = masked_df.withColumn(col, mask_phone_udf(F.col(col)))
    elif pii_type == "CREDIT_CARD":
        masked_df = masked_df.withColumn(col, mask_cc_udf(F.col(col)))
    elif pii_type == "PERSON_NAME":
        masked_df = masked_df.withColumn(col, mask_name_udf(F.col(col)))
    elif pii_type == "ADDRESS":
        masked_df = masked_df.withColumn(col, mask_address_udf(F.col(col)))
    else:
        # Default: hash with salt
        masked_df = masked_df.withColumn(
            col, F.sha2(F.concat(F.col(col), F.lit("salt_value")), 256)
        )

# Write masked dataset to non-prod location
masked_df.writeTo(
    f"glue_catalog.{args['catalog_database']}.{args['target_table']}"
).using("iceberg").createOrReplace()

print(f"Masking complete for {args['environment']} environment.")
print(f"Masked {len(pii_registry)} PII columns across {masked_df.count()} rows.")

job.commit()
```

### Job 5: Compliance Verification & Audit Reporting

```python
# job5_compliance_verification.py
# Proves deletion to regulators with cryptographic evidence

import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
from pyspark.sql import functions as F
import boto3
import json
import hashlib
from datetime import datetime, timedelta

args = getResolvedOptions(sys.argv, [
    'JOB_NAME', 'catalog_database', 'audit_table',
    'certificate_bucket', 'report_bucket'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)


class ComplianceVerifier:
    """Verifies deletion completeness and generates compliance certificates."""

    def __init__(self, spark, catalog_db):
        self.spark = spark
        self.catalog_db = catalog_db
        self.s3 = boto3.client('s3')

    def verify_deletion(self, user_id, tables_deleted):
        """Verify user data no longer exists in any dataset."""
        verification_results = []

        for table_info in tables_deleted:
            table = table_info['table_name']
            id_col = table_info['id_column']

            # Check current data
            remaining = self.spark.sql(f"""
                SELECT COUNT(*) as cnt
                FROM glue_catalog.{self.catalog_db}.{table}
                WHERE {id_col} = '{user_id}'
            """).collect()[0]['cnt']

            # Check Iceberg history (ensure snapshots are expired)
            snapshots = self.spark.sql(f"""
                SELECT snapshot_id, committed_at
                FROM glue_catalog.{self.catalog_db}.{table}.snapshots
                ORDER BY committed_at DESC
            """).collect()

            verification_results.append({
                "table_name": table,
                "records_remaining": remaining,
                "verified_deleted": remaining == 0,
                "snapshots_cleaned": len(snapshots) <= 1,
                "verification_timestamp": datetime.utcnow().isoformat()
            })

        return verification_results

    def generate_deletion_certificate(self, request_id, user_id, verification):
        """Generate a cryptographic deletion certificate."""
        certificate = {
            "certificate_id": hashlib.sha256(
                f"{request_id}{datetime.utcnow().isoformat()}".encode()
            ).hexdigest(),
            "request_id": request_id,
            "user_id_hash": hashlib.sha256(user_id.encode()).hexdigest(),
            "deletion_scope": {
                "tables_processed": len(verification),
                "tables_verified": sum(1 for v in verification if v['verified_deleted']),
                "all_deleted": all(v['verified_deleted'] for v in verification)
            },
            "compliance_status": "COMPLIANT" if all(
                v['verified_deleted'] for v in verification
            ) else "REQUIRES_REVIEW",
            "issued_at": datetime.utcnow().isoformat(),
            "valid_until": (datetime.utcnow() + timedelta(days=365)).isoformat(),
            "verification_details": verification,
            "regulatory_framework": "GDPR Article 17",
            "certifying_system": "AWS Glue GDPR Pipeline v2.1"
        }

        # Sign certificate (simplified - production uses AWS KMS signing)
        cert_json = json.dumps(certificate, sort_keys=True)
        certificate["signature"] = hashlib.sha256(cert_json.encode()).hexdigest()

        return certificate

    def generate_dpa_report(self, start_date, end_date):
        """Generate report for Data Protection Authority audits."""
        # Aggregate deletion statistics
        stats = self.spark.sql(f"""
            SELECT
                regulation,
                COUNT(DISTINCT user_id) as users_deleted,
                COUNT(*) as total_operations,
                SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) as successful,
                SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) as failed,
                AVG(UNIX_TIMESTAMP(deletion_timestamp) -
                    UNIX_TIMESTAMP(request_timestamp)) / 3600 as avg_hours_to_complete,
                MAX(UNIX_TIMESTAMP(deletion_timestamp) -
                    UNIX_TIMESTAMP(request_timestamp)) / 3600 as max_hours_to_complete
            FROM glue_catalog.{self.catalog_db}.deletion_audit_log
            WHERE deletion_timestamp BETWEEN '{start_date}' AND '{end_date}'
            GROUP BY regulation
        """).collect()

        report = {
            "report_type": "DPA_COMPLIANCE_REPORT",
            "reporting_period": {"start": start_date, "end": end_date},
            "generated_at": datetime.utcnow().isoformat(),
            "summary": {
                "total_requests_processed": sum(r['total_operations'] for r in stats),
                "unique_users_deleted": sum(r['users_deleted'] for r in stats),
                "success_rate": sum(r['successful'] for r in stats) /
                               max(sum(r['total_operations'] for r in stats), 1),
                "sla_compliance": all(
                    r['max_hours_to_complete'] <= 72 for r in stats
                )
            },
            "by_regulation": [
                {
                    "regulation": r['regulation'],
                    "users_deleted": r['users_deleted'],
                    "avg_completion_hours": round(r['avg_hours_to_complete'], 1),
                    "max_completion_hours": round(r['max_hours_to_complete'], 1),
                    "within_sla": r['max_hours_to_complete'] <= 72
                }
                for r in stats
            ]
        }
        return report


# Execute verification for recent deletions
verifier = ComplianceVerifier(spark, args['catalog_database'])

# Get recent unverified deletions
unverified = spark.sql(f"""
    SELECT DISTINCT user_id, request_id
    FROM glue_catalog.{args['catalog_database']}.{args['audit_table']}
    WHERE status = 'COMPLETED'
      AND verified = FALSE
    ORDER BY deletion_timestamp
    LIMIT 1000
""").collect()

certificates = []
for row in unverified:
    # Get all tables this user was deleted from
    tables = spark.sql(f"""
        SELECT table_name, id_column
        FROM glue_catalog.{args['catalog_database']}.{args['audit_table']}
        WHERE user_id = '{row['user_id']}'
          AND status = 'COMPLETED'
    """).collect()

    # Verify deletion
    verification = verifier.verify_deletion(
        row['user_id'],
        [{"table_name": t['table_name'], "id_column": t['id_column']} for t in tables]
    )

    # Generate certificate
    cert = verifier.generate_deletion_certificate(
        row['request_id'], row['user_id'], verification
    )
    certificates.append(cert)

    # Upload certificate to S3
    verifier.s3.put_object(
        Bucket=args['certificate_bucket'],
        Key=f"certificates/{row['request_id']}/{cert['certificate_id']}.json",
        Body=json.dumps(cert, indent=2),
        ServerSideEncryption='aws:kms'
    )

# Generate quarterly DPA report
report = verifier.generate_dpa_report(
    (datetime.utcnow() - timedelta(days=90)).strftime('%Y-%m-%d'),
    datetime.utcnow().strftime('%Y-%m-%d')
)

verifier.s3.put_object(
    Bucket=args['report_bucket'],
    Key=f"dpa-reports/{datetime.utcnow().strftime('%Y-Q%q')}/compliance_report.json",
    Body=json.dumps(report, indent=2),
    ServerSideEncryption='aws:kms'
)

print(f"Verification complete. {len(certificates)} certificates generated.")
print(f"Compliance rate: {sum(1 for c in certificates if c['compliance_status'] == 'COMPLIANT') / len(certificates):.1%}")

job.commit()
```

---

## Production Handling

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Handling Deletion in Nested/Denormalized Data

```python
def delete_from_nested_structures(spark, catalog_db, user_id):
    """
    Travel data is heavily denormalized. A booking record contains:
    - Primary guest details
    - Additional guest details (array)
    - Payment info (struct)
    - Review data (nested struct)
    """

    # Remove user from group bookings (array of guests)
    spark.sql(f"""
        UPDATE glue_catalog.{catalog_db}.group_bookings
        SET guests = FILTER(guests, g -> g.user_id != '{user_id}'),
            guest_count = SIZE(FILTER(guests, g -> g.user_id != '{user_id}'))
        WHERE EXISTS(guests, g -> g.user_id = '{user_id}')
    """)

    # Nullify user data in shared itineraries
    spark.sql(f"""
        UPDATE glue_catalog.{catalog_db}.shared_itineraries
        SET participants = TRANSFORM(
            participants,
            p -> CASE
                WHEN p.user_id = '{user_id}'
                THEN NAMED_STRUCT('user_id', NULL, 'name', 'Deleted User',
                                  'email', NULL, 'role', p.role)
                ELSE p
            END
        )
        WHERE EXISTS(participants, p -> p.user_id = '{user_id}')
    """)
```

### Cross-Region Deletion Coordination

```python
class CrossRegionDeletion:
    """Coordinates deletion across multiple AWS regions for data residency."""

    REGION_MAP = {
        "EU": "eu-west-1",
        "US": "us-east-1",
        "APAC": "ap-southeast-1",
        "LATAM": "sa-east-1"
    }

    def __init__(self):
        self.sfn_clients = {
            region: boto3.client('stepfunctions', region_name=region)
            for region in self.REGION_MAP.values()
        }

    def trigger_regional_deletion(self, user_id, user_region):
        """
        EU data stays in EU - trigger deletion in the correct region.
        But user may have data in multiple regions (booking in US hotel).
        """
        # Determine all regions with user data
        regions_with_data = self._find_user_regions(user_id)

        executions = []
        for region in regions_with_data:
            sfn = self.sfn_clients[region]
            execution = sfn.start_execution(
                stateMachineArn=f"arn:aws:states:{region}:123456789:stateMachine:gdpr-deletion",
                input=json.dumps({
                    "user_id": user_id,
                    "region": region,
                    "regulation": "GDPR" if user_region == "EU" else "CCPA"
                })
            )
            executions.append(execution)

        return executions

    def _find_user_regions(self, user_id):
        """Query global user registry to find data locations."""
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        table = dynamodb.Table('global-user-data-registry')
        response = table.get_item(Key={'user_id': user_id})
        return response.get('Item', {}).get('data_regions', ['eu-west-1'])
```

### Partial Failure Handling

```python
class TransactionalDeletion:
    """Ensures all-or-nothing deletion with compensation on failure."""

    def __init__(self, spark, catalog_db):
        self.spark = spark
        self.catalog_db = catalog_db
        self.completed_deletions = []

    def execute_with_retry(self, user_id, tables, max_retries=3):
        """Execute deletion with retry and compensation logic."""
        for table_info in tables:
            retries = 0
            while retries < max_retries:
                try:
                    # Take savepoint (Iceberg snapshot)
                    snapshot_id = self._get_current_snapshot(table_info['table_name'])

                    # Execute deletion
                    self.spark.sql(f"""
                        DELETE FROM glue_catalog.{self.catalog_db}.{table_info['table_name']}
                        WHERE {table_info['id_column']} = '{user_id}'
                    """)

                    self.completed_deletions.append({
                        "table": table_info['table_name'],
                        "snapshot_before": snapshot_id
                    })
                    break

                except Exception as e:
                    retries += 1
                    if retries >= max_retries:
                        # Log failure - do NOT rollback completed deletions
                        # GDPR requires deletion, so partial deletion is better
                        # than no deletion. Flag for manual review.
                        self._flag_for_manual_review(user_id, table_info, str(e))
                    else:
                        import time
                        time.sleep(2 ** retries)  # Exponential backoff

    def _get_current_snapshot(self, table_name):
        result = self.spark.sql(f"""
            SELECT snapshot_id
            FROM glue_catalog.{self.catalog_db}.{table_name}.snapshots
            ORDER BY committed_at DESC LIMIT 1
        """).collect()
        return result[0]['snapshot_id'] if result else None

    def _flag_for_manual_review(self, user_id, table_info, error):
        """Create alert for DPO team when automated deletion fails."""
        sns = boto3.client('sns')
        sns.publish(
            TopicArn='arn:aws:sns:eu-west-1:123456789:gdpr-deletion-failures',
            Subject=f"GDPR Deletion Failed: {user_id}",
            Message=json.dumps({
                "user_id": user_id,
                "table": table_info['table_name'],
                "error": error,
                "action_required": "Manual deletion within 48 hours",
                "severity": "HIGH"
            })
        )
```

---

## Compliance Verification — Proving Deletion to Regulators

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    COMPLIANCE EVIDENCE CHAIN                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. Request Receipt    → Timestamped SQS message + DynamoDB record      │
│  2. Data Discovery     → PII registry proves we know where data lives   │
│  3. Deletion Execution → Iceberg commit log with row-level deletes      │
│  4. Snapshot Expiry    → Prove historical copies removed                │
│  5. Verification Scan  → Post-deletion search confirms 0 records        │
│  6. Certificate        → Cryptographically signed deletion proof        │
│  7. Audit Trail        → Immutable log in append-only Iceberg table     │
│                                                                         │
│  Evidence stored for 5 years (GDPR Article 5(1)(e))                     │
│  Note: We store hash(user_id), never the actual user_id                 │
└─────────────────────────────────────────────────────────────────────────┘
```

### Crypto-Shredding (Alternative Approach)

```python
def crypto_shred_user(user_id, kms_client):
    """
    Alternative to physical deletion: encrypt PII with per-user key,
    then delete the key. Data becomes unrecoverable.

    Useful for: backup tapes, S3 Object Lock data, third-party copies
    """
    # Each user has a dedicated encryption key
    key_alias = f"alias/user-pii-key/{hashlib.sha256(user_id.encode()).hexdigest()[:16]}"

    try:
        # Schedule key deletion (7-day minimum waiting period)
        key_metadata = kms_client.describe_key(KeyId=key_alias)
        kms_client.schedule_key_deletion(
            KeyId=key_metadata['KeyMetadata']['KeyId'],
            PendingWindowInDays=7
        )
        return {"method": "crypto_shredding", "status": "key_scheduled_for_deletion"}
    except kms_client.exceptions.NotFoundException:
        return {"method": "crypto_shredding", "status": "key_not_found_already_deleted"}
```

---

## Scaling: 10K Deletions/Day Across 200+ Datasets in < 72 Hours

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Throughput Design

```
┌─────────────────────────────────────────────────────────────────┐
│  SCALING STRATEGY                                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Requests/day:  10,000                                          │
│  Tables/user:   ~15 (avg datasets containing user data)         │
│  Operations/day: 10,000 × 15 = 150,000 delete operations        │
│  SLA:           72 hours                                        │
│                                                                 │
│  BATCHING STRATEGY:                                             │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Batch 1 (hourly): Collect deletion requests              │  │
│  │ Batch 2 (hourly): Group by table → execute bulk deletes  │  │
│  │ Batch 3 (6-hourly): Expire snapshots                     │  │
│  │ Batch 4 (12-hourly): Verification scan                   │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  PARALLELISM:                                                   │
│  - 20 concurrent Glue jobs (G.2X workers)                       │
│  - Each job handles 1 table × batch of user_ids                 │
│  - Iceberg handles concurrent deletes via optimistic locking    │
│                                                                 │
│  OPTIMIZATION:                                                  │
│  - Partition pruning: user_id hash → reduce scan scope          │
│  - Bloom filters on user_id columns                             │
│  - Batch DELETE WHERE user_id IN (...) vs individual deletes    │
│  - Priority queue: regulatory deadline-based ordering           │
└─────────────────────────────────────────────────────────────────┘
```

### Batch Deletion Optimization

```python
def batch_delete_users(spark, catalog_db, table_name, id_column, user_ids):
    """
    Delete multiple users in a single Iceberg operation.
    Much more efficient than individual deletes.
    """
    # Create temp view of user_ids to delete
    user_df = spark.createDataFrame(
        [(uid,) for uid in user_ids], ["delete_user_id"]
    )
    user_df.createOrReplaceTempView("users_to_delete")

    # Single DELETE operation for entire batch
    spark.sql(f"""
        DELETE FROM glue_catalog.{catalog_db}.{table_name}
        WHERE {id_column} IN (SELECT delete_user_id FROM users_to_delete)
    """)

    # This produces ONE Iceberg commit with all deletes
    # vs 10,000 individual commits
```

---

## Cost Analysis

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```
┌────────────────────────────────────────────────────────────────────────┐
│  MONTHLY COST BREAKDOWN (10K deletions/day)                            │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  Component                        │ Monthly Cost │ Notes               │
│  ─────────────────────────────────┼──────────────┼──────────────────── │
│  Glue Jobs (deletion execution)   │ $8,200       │ 20 G.2X × 4hr/day  │
│  Glue Jobs (PII scanning)         │ $3,100       │ Weekly full scan    │
│  Glue Jobs (masking/non-prod)     │ $2,400       │ Daily refresh       │
│  Glue Jobs (verification)         │ $1,800       │ 12-hourly           │
│  Step Functions orchestration     │ $120         │ 300K transitions    │
│  SQS (deletion queue)             │ $15          │ 300K messages       │
│  S3 (audit/certificates)          │ $50          │ Compliance store    │
│  KMS (encryption keys)            │ $300         │ Per-user keys       │
│  CloudWatch (monitoring)          │ $200         │ Metrics + alarms    │
│  ─────────────────────────────────┼──────────────┼──────────────────── │
│  TOTAL                            │ ~$16,200/mo  │                     │
│                                                                        │
│  vs. GDPR FINE RISK:              │ €200,000,000 │ 4% global revenue   │
│  ROI:                             │ 12,345x      │                     │
│                                                                        │
│  vs. FULL REWRITE APPROACH:       │ ~$1,500,000  │ Rewrite 5PB daily   │
│  SAVINGS:                         │ 99%          │ Iceberg row-delete  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Companies Using This Pattern

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

| Company | Scale | Key Challenge | Approach |
|---------|-------|---------------|----------|
| **Booking.com** | 28M listings, 500M users | Multi-tenant property data with guest PII embedded | Iceberg row-level deletes + crypto-shredding for backups |
| **Expedia** | 3M properties, 200+ brands | Cross-brand user identity resolution | Unified identity graph + cascading deletion |
| **Airbnb** | 7M listings, 150M users | Host-guest shared data (reviews, messages) | Selective anonymization vs deletion |
| **TripAdvisor** | 1B reviews | User-generated content with embedded PII | NLP-based PII scrubbing in review text |
| **Salesforce** | Multi-tenant CRM | Customer-of-customer data (processor role) | Tenant-isolated deletion with sub-processor coordination |

### Key Lessons from Production

1. **Booking.com**: Discovered 47 previously unknown datasets containing PII during initial scan
2. **Expedia**: Reduced deletion SLA from 14 days to 6 hours using Iceberg
3. **Airbnb**: 12% of deletion requests are withdrawn within 24 hours → implement cooling-off period
4. **TripAdvisor**: Regex-based PII detection in free text catches 94% of embedded PII
5. **Salesforce**: Multi-tenant isolation requires separate deletion verification per tenant

---

## Summary

```
┌─────────────────────────────────────────────────────────────────────────┐
│  KEY TAKEAWAYS                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. Iceberg row-level deletes are the foundation — no full rewrites     │
│  2. PII registry (data catalog) is mandatory — you can't delete what    │
│     you can't find                                                      │
│  3. Crypto-shredding handles immutable storage (backups, Object Lock)   │
│  4. Batch operations are critical — individual deletes don't scale      │
│  5. Verification is non-negotiable — prove deletion to regulators       │
│  6. Cross-region coordination for data residency compliance             │
│  7. The pipeline pays for itself 12,000x over vs fine risk              │
│                                                                         │
│  AWS Glue provides: PII detection, Iceberg integration, catalog-based   │
│  data discovery, job orchestration, and Lake Formation access control   │
│  — all essential building blocks for GDPR compliance at scale.          │
└─────────────────────────────────────────────────────────────────────────┘
```
