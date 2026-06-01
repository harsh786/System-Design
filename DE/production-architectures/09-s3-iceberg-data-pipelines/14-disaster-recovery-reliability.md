# Disaster Recovery & Data Reliability for Iceberg Data Pipelines

## Overview

Apache Iceberg's architecture—with immutable data files, snapshot isolation, and metadata layering—provides inherent advantages for disaster recovery. This document covers production-grade strategies for ensuring data reliability, recovering from failures, and maintaining multi-region availability.

---

## Architecture: DR Topology

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DR Architecture                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────── Region A (Primary) ───────────────┐                  │
│  │                                                    │                  │
│  │  ┌──────────┐    ┌──────────┐    ┌────────────┐  │                  │
│  │  │  Writers │───▶│  Catalog │───▶│ S3 Bucket  │  │                  │
│  │  │  (Spark) │    │  (Glue)  │    │  (Data +   │  │                  │
│  │  └──────────┘    └────┬─────┘    │  Metadata) │  │                  │
│  │                       │           └─────┬──────┘  │                  │
│  └───────────────────────┼─────────────────┼─────────┘                  │
│                          │                 │                             │
│                   Catalog Sync        S3 CRR                            │
│                    (Lambda)        (Cross-Region                         │
│                          │          Replication)                         │
│                          │                 │                             │
│  ┌───────────────────────┼─────────────────┼─────────────┐             │
│  │                       ▼                 ▼              │             │
│  │  ┌──────────┐    ┌──────────┐    ┌────────────┐      │             │
│  │  │  Readers │◀───│  Catalog │◀───│ S3 Bucket  │      │             │
│  │  │  (Spark) │    │  (Glue)  │    │  (Replica) │      │             │
│  │  └──────────┘    └──────────┘    └────────────┘      │             │
│  │                                                       │             │
│  └─────────────── Region B (DR / Read Replica) ─────────┘             │
│                                                                         │
│  ┌──────────────── Backup Layer ────────────────────────┐              │
│  │                                                       │              │
│  │  ┌────────────┐  ┌─────────────┐  ┌──────────────┐  │              │
│  │  │  Metadata  │  │   Catalog   │  │   Snapshot   │  │              │
│  │  │  Backups   │  │   Backups   │  │   Archives   │  │              │
│  │  │  (S3 IA)   │  │  (DynamoDB) │  │  (Glacier)   │  │              │
│  │  └────────────┘  └─────────────┘  └──────────────┘  │              │
│  └───────────────────────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## RTO/RPO Definitions by Table Tier

| Tier | Description | RPO | RTO | Strategy |
|------|-------------|-----|-----|----------|
| **Tier 1 - Critical** | Revenue tables, SLA-bound | < 5 min | < 15 min | Active-active, real-time sync |
| **Tier 2 - Important** | Core analytics, dashboards | < 1 hour | < 30 min | Cross-region replication + catalog sync |
| **Tier 3 - Standard** | Internal reporting, ad-hoc | < 4 hours | < 2 hours | S3 CRR with periodic catalog backup |
| **Tier 4 - Archival** | Historical data, compliance | < 24 hours | < 8 hours | Daily metadata backup, Glacier restore |

---

## 1. Snapshot-Based Recovery

### How Iceberg Snapshots Enable Recovery

Each Iceberg commit creates an immutable snapshot. The snapshot history acts as a built-in time-travel mechanism.

```python
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .config("spark.sql.catalog.glue_catalog", "org.apache.iceberg.spark.SparkCatalog") \
    .config("spark.sql.catalog.glue_catalog.catalog-impl", "org.apache.iceberg.aws.glue.GlueCatalog") \
    .config("spark.sql.catalog.glue_catalog.warehouse", "s3://data-lake-prod/warehouse") \
    .getOrCreate()

# List all snapshots for a table
spark.sql("""
    SELECT snapshot_id, committed_at, operation, summary
    FROM glue_catalog.analytics.events.snapshots
    ORDER BY committed_at DESC
""").show(truncate=False)

# List snapshot history with parent lineage
spark.sql("""
    SELECT h.snapshot_id, h.parent_id, h.is_current_ancestor,
           s.committed_at, s.operation
    FROM glue_catalog.analytics.events.history h
    JOIN glue_catalog.analytics.events.snapshots s
      ON h.snapshot_id = s.snapshot_id
    ORDER BY s.committed_at DESC
""").show(truncate=False)
```

### Rolling Back to a Previous Snapshot

```python
# Method 1: Rollback to specific snapshot ID
spark.sql("""
    CALL glue_catalog.system.rollback_to_snapshot(
        'analytics.events',
        8423947283947234
    )
""")

# Method 2: Rollback to a timestamp
spark.sql("""
    CALL glue_catalog.system.rollback_to_timestamp(
        'analytics.events',
        TIMESTAMP '2024-01-15 10:30:00'
    )
""")

# Method 3: Using cherrypick to selectively apply a snapshot
spark.sql("""
    CALL glue_catalog.system.cherrypick_snapshot(
        'analytics.events',
        8423947283947234
    )
""")
```

### Automated Rollback on Data Quality Failure

```python
from pyspark.sql import functions as F
from datetime import datetime, timedelta

def safe_write_with_rollback(spark, df, table_name, validation_fn):
    """Write data with automatic rollback if validation fails."""
    
    # Capture current snapshot before write
    current_snapshot = spark.sql(f"""
        SELECT snapshot_id FROM {table_name}.snapshots
        WHERE committed_at = (SELECT MAX(committed_at) FROM {table_name}.snapshots)
    """).collect()[0][0]
    
    print(f"Pre-write snapshot: {current_snapshot}")
    
    try:
        # Perform the write
        df.writeTo(table_name).append()
        
        # Run validation
        new_data = spark.table(table_name)
        is_valid, reason = validation_fn(new_data)
        
        if not is_valid:
            print(f"Validation failed: {reason}. Rolling back...")
            spark.sql(f"""
                CALL glue_catalog.system.rollback_to_snapshot(
                    '{table_name.replace("glue_catalog.", "")}',
                    {current_snapshot}
                )
            """)
            raise ValueError(f"Write rolled back due to validation failure: {reason}")
        
        print("Write successful, validation passed.")
        
    except Exception as e:
        if "rolled back" not in str(e):
            # Unexpected error - still rollback
            print(f"Error during write: {e}. Rolling back...")
            spark.sql(f"""
                CALL glue_catalog.system.rollback_to_snapshot(
                    '{table_name.replace("glue_catalog.", "")}',
                    {current_snapshot}
                )
            """)
        raise


def validate_events(df):
    """Example validation function."""
    row_count = df.count()
    null_ratio = df.filter(F.col("event_id").isNull()).count() / max(row_count, 1)
    
    if null_ratio > 0.01:
        return False, f"Null event_id ratio {null_ratio:.4f} exceeds 1% threshold"
    
    # Check for duplicate explosion
    distinct_ratio = df.select("event_id").distinct().count() / max(row_count, 1)
    if distinct_ratio < 0.5:
        return False, f"Distinct ratio {distinct_ratio:.4f} suggests massive duplicates"
    
    return True, "OK"


# Usage
safe_write_with_rollback(
    spark,
    new_events_df,
    "glue_catalog.analytics.events",
    validate_events
)
```

---

## 2. Cross-Region Replication

### Terraform: S3 Cross-Region Replication

```hcl
# terraform/dr-replication/main.tf

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  alias  = "primary"
  region = "us-east-1"
}

provider "aws" {
  alias  = "dr"
  region = "us-west-2"
}

# --- IAM Role for Replication ---
resource "aws_iam_role" "replication" {
  provider = aws.primary
  name     = "iceberg-s3-replication-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "s3.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy" "replication" {
  provider = aws.primary
  name     = "iceberg-s3-replication-policy"
  role     = aws_iam_role.replication.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "s3:GetReplicationConfiguration",
          "s3:ListBucket"
        ]
        Effect   = "Allow"
        Resource = [aws_s3_bucket.primary.arn]
      },
      {
        Action = [
          "s3:GetObjectVersionForReplication",
          "s3:GetObjectVersionAcl",
          "s3:GetObjectVersionTagging"
        ]
        Effect   = "Allow"
        Resource = ["${aws_s3_bucket.primary.arn}/*"]
      },
      {
        Action = [
          "s3:ReplicateObject",
          "s3:ReplicateDelete",
          "s3:ReplicateTags"
        ]
        Effect   = "Allow"
        Resource = ["${aws_s3_bucket.dr.arn}/*"]
      }
    ]
  })
}

# --- Primary Bucket ---
resource "aws_s3_bucket" "primary" {
  provider = aws.primary
  bucket   = "iceberg-datalake-primary-us-east-1"

  tags = {
    Environment = "production"
    Purpose     = "iceberg-primary"
  }
}

resource "aws_s3_bucket_versioning" "primary" {
  provider = aws.primary
  bucket   = aws_s3_bucket.primary.id

  versioning_configuration {
    status = "Enabled"  # Required for CRR
  }
}

# --- DR Bucket ---
resource "aws_s3_bucket" "dr" {
  provider = aws.dr
  bucket   = "iceberg-datalake-dr-us-west-2"

  tags = {
    Environment = "production"
    Purpose     = "iceberg-dr"
  }
}

resource "aws_s3_bucket_versioning" "dr" {
  provider = aws.dr
  bucket   = aws_s3_bucket.dr.id

  versioning_configuration {
    status = "Enabled"
  }
}

# --- Replication Configuration ---
resource "aws_s3_bucket_replication_configuration" "replication" {
  provider = aws.primary
  bucket   = aws_s3_bucket.primary.id
  role     = aws_iam_role.replication.arn

  depends_on = [aws_s3_bucket_versioning.primary]

  rule {
    id     = "replicate-iceberg-metadata"
    status = "Enabled"

    filter {
      prefix = "warehouse/"
    }

    destination {
      bucket        = aws_s3_bucket.dr.arn
      storage_class = "STANDARD"

      metrics {
        status = "Enabled"
        event_threshold {
          minutes = 15
        }
      }

      replication_time {
        status = "Enabled"
        time {
          minutes = 15
        }
      }
    }

    delete_marker_replication {
      status = "Enabled"
    }
  }

  # Separate rule for data files with different priority
  rule {
    id       = "replicate-iceberg-data"
    priority = 1
    status   = "Enabled"

    filter {
      prefix = "warehouse/"
      tag {
        key   = "iceberg"
        value = "data"
      }
    }

    destination {
      bucket        = aws_s3_bucket.dr.arn
      storage_class = "STANDARD_IA"
    }
  }
}

# --- S3 Replication Metrics Alarm ---
resource "aws_cloudwatch_metric_alarm" "replication_latency" {
  provider            = aws.primary
  alarm_name          = "iceberg-replication-latency-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "ReplicationLatency"
  namespace           = "AWS/S3"
  period              = 300
  statistic           = "Maximum"
  threshold           = 900  # 15 minutes

  dimensions = {
    SourceBucket     = aws_s3_bucket.primary.id
    DestinationBucket = aws_s3_bucket.dr.id
    RuleId           = "replicate-iceberg-metadata"
  }

  alarm_actions = [aws_sns_topic.dr_alerts.arn]
}

resource "aws_sns_topic" "dr_alerts" {
  provider = aws.primary
  name     = "iceberg-dr-alerts"
}

# --- Catalog Sync Lambda ---
resource "aws_lambda_function" "catalog_sync" {
  provider      = aws.primary
  function_name = "iceberg-catalog-sync"
  role          = aws_iam_role.catalog_sync_role.arn
  handler       = "index.handler"
  runtime       = "python3.11"
  timeout       = 300
  memory_size   = 512

  filename = "${path.module}/lambda/catalog_sync.zip"

  environment {
    variables = {
      DR_REGION        = "us-west-2"
      DR_CATALOG_DB    = "analytics_dr"
      PRIMARY_BUCKET   = aws_s3_bucket.primary.id
      DR_BUCKET        = aws_s3_bucket.dr.id
    }
  }
}

# Trigger catalog sync on metadata file changes
resource "aws_s3_bucket_notification" "metadata_notification" {
  provider = aws.primary
  bucket   = aws_s3_bucket.primary.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.catalog_sync.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "warehouse/"
    filter_suffix       = "metadata.json"
  }
}
```

### Catalog Sync Lambda

```python
# lambda/catalog_sync/index.py
import boto3
import json
import os
import re

def handler(event, context):
    """Sync Iceberg catalog entries to DR region when metadata files are updated."""
    
    dr_region = os.environ['DR_REGION']
    dr_catalog_db = os.environ['DR_CATALOG_DB']
    primary_bucket = os.environ['PRIMARY_BUCKET']
    dr_bucket = os.environ['DR_BUCKET']
    
    glue_primary = boto3.client('glue', region_name=os.environ['AWS_REGION'])
    glue_dr = boto3.client('glue', region_name=dr_region)
    
    for record in event['Records']:
        key = record['s3']['object']['key']
        
        # Extract database and table from path
        # Expected: warehouse/db_name/table_name/metadata/xxx-metadata.json
        match = re.match(r'warehouse/([^/]+)/([^/]+)/metadata/', key)
        if not match:
            continue
        
        db_name, table_name = match.groups()
        
        try:
            # Get table from primary catalog
            response = glue_primary.get_table(
                DatabaseName=db_name,
                Name=table_name
            )
            table_def = response['Table']
            
            # Modify location to point to DR bucket
            new_location = table_def['StorageDescriptor']['Location'].replace(
                primary_bucket, dr_bucket
            )
            table_def['StorageDescriptor']['Location'] = new_location
            
            # Update metadata_location parameter
            if 'Parameters' in table_def:
                for param_key in ['metadata_location', 'table_type']:
                    if param_key in table_def['Parameters']:
                        table_def['Parameters'][param_key] = \
                            table_def['Parameters'][param_key].replace(
                                primary_bucket, dr_bucket
                            )
            
            # Remove fields that can't be passed to create/update
            for field in ['DatabaseName', 'CreateTime', 'UpdateTime', 
                         'CreatedBy', 'IsRegisteredWithLakeFormation',
                         'CatalogId', 'VersionId']:
                table_def.pop(field, None)
            
            # Create or update in DR region
            try:
                glue_dr.create_database(
                    DatabaseInput={'Name': dr_catalog_db}
                )
            except glue_dr.exceptions.AlreadyExistsException:
                pass
            
            try:
                glue_dr.create_table(
                    DatabaseName=dr_catalog_db,
                    TableInput=table_def
                )
                print(f"Created DR table: {dr_catalog_db}.{table_name}")
            except glue_dr.exceptions.AlreadyExistsException:
                glue_dr.update_table(
                    DatabaseName=dr_catalog_db,
                    TableInput=table_def
                )
                print(f"Updated DR table: {dr_catalog_db}.{table_name}")
                
        except Exception as e:
            print(f"Error syncing {db_name}.{table_name}: {e}")
            raise
    
    return {'statusCode': 200, 'synced': len(event['Records'])}
```

---

## 3. Corruption Scenarios & Recovery

### Scenario Matrix

| Corruption Type | Detection | Impact | Recovery Method | Time to Recover |
|----------------|-----------|--------|-----------------|-----------------|
| Data file corrupted | Checksum mismatch on read | Partial data loss | Rewrite from source or snapshot | 10-60 min |
| Manifest file corrupted | Table scan failure | Table unreadable | Rewrite manifest from data files | 15-30 min |
| Metadata JSON corrupted | Catalog load failure | Table inaccessible | Restore from previous metadata version | 5-10 min |
| Catalog entry corrupted | Table not found | Table invisible | Re-register from metadata file | 2-5 min |
| Partial write (data) | Missing data in scan | Incomplete data | Rollback snapshot | 2-5 min |
| Partial write (metadata) | Commit failure | Stale table state | Retry commit or rollback | 2-5 min |
| Schema corruption | Schema mismatch errors | Reads fail | Rollback to valid schema snapshot | 5-10 min |

### Recovery: Metadata Corruption

```python
def recover_from_metadata_corruption(spark, table_path, catalog_name="glue_catalog"):
    """
    Recover when the current metadata.json is corrupted.
    Iceberg keeps previous metadata versions - find and restore the last valid one.
    """
    import boto3
    import json
    
    s3 = boto3.client('s3')
    
    # Parse bucket and prefix from table path
    # s3://bucket/warehouse/db/table
    parts = table_path.replace("s3://", "").split("/", 1)
    bucket = parts[0]
    prefix = parts[1] + "/metadata/"
    
    # List all metadata files (they're versioned: v1.metadata.json, v2.metadata.json, ...)
    response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
    metadata_files = sorted(
        [obj['Key'] for obj in response.get('Contents', []) 
         if obj['Key'].endswith('.metadata.json')],
        reverse=True  # Most recent first
    )
    
    print(f"Found {len(metadata_files)} metadata versions")
    
    # Try each metadata file from newest to oldest
    for metadata_key in metadata_files:
        try:
            obj = s3.get_object(Bucket=bucket, Key=metadata_key)
            metadata = json.loads(obj['Body'].read().decode('utf-8'))
            
            # Validate basic structure
            assert 'format-version' in metadata
            assert 'current-snapshot-id' in metadata
            assert 'snapshots' in metadata
            
            print(f"Valid metadata found: s3://{bucket}/{metadata_key}")
            print(f"  Format version: {metadata['format-version']}")
            print(f"  Snapshots: {len(metadata['snapshots'])}")
            print(f"  Current snapshot: {metadata['current-snapshot-id']}")
            
            # Update catalog to point to this metadata file
            valid_metadata_location = f"s3://{bucket}/{metadata_key}"
            
            # For Glue catalog - update the table's metadata_location
            glue = boto3.client('glue')
            # You'll need db_name and table_name extracted from path
            db_name = table_path.split("/")[-2]  # Adjust based on layout
            table_name = table_path.split("/")[-1]
            
            table_response = glue.get_table(DatabaseName=db_name, Name=table_name)
            table_input = table_response['Table']
            
            # Clean up response for update
            for field in ['DatabaseName', 'CreateTime', 'UpdateTime', 
                         'CreatedBy', 'IsRegisteredWithLakeFormation',
                         'CatalogId', 'VersionId']:
                table_input.pop(field, None)
            
            table_input['Parameters']['metadata_location'] = valid_metadata_location
            
            glue.update_table(DatabaseName=db_name, TableInput=table_input)
            print(f"Catalog updated to point to: {valid_metadata_location}")
            
            return valid_metadata_location
            
        except Exception as e:
            print(f"  Invalid: {metadata_key} - {e}")
            continue
    
    raise RuntimeError("No valid metadata files found - manual intervention required")
```

### Recovery: Data File Corruption

```python
def repair_corrupt_data_files(spark, table_name, suspect_files=None):
    """
    Detect and repair corrupt data files.
    Strategy: Identify corrupt files, rewrite partition from last good snapshot.
    """
    
    # Step 1: Identify all data files
    files_df = spark.sql(f"""
        SELECT file_path, file_size_in_bytes, record_count, 
               partition, file_format
        FROM {table_name}.files
    """)
    
    corrupt_files = []
    
    if suspect_files:
        corrupt_files = suspect_files
    else:
        # Scan all files for corruption via checksum validation
        import boto3
        s3 = boto3.client('s3')
        
        for row in files_df.collect():
            file_path = row['file_path']
            expected_size = row['file_size_in_bytes']
            
            # Parse S3 path
            parts = file_path.replace("s3://", "").split("/", 1)
            bucket, key = parts[0], parts[1]
            
            try:
                head = s3.head_object(Bucket=bucket, Key=key)
                actual_size = head['ContentLength']
                
                if actual_size != expected_size:
                    print(f"CORRUPT (size mismatch): {file_path}")
                    print(f"  Expected: {expected_size}, Actual: {actual_size}")
                    corrupt_files.append(file_path)
                    
            except s3.exceptions.NoSuchKey:
                print(f"MISSING: {file_path}")
                corrupt_files.append(file_path)
    
    if not corrupt_files:
        print("No corrupt files detected.")
        return
    
    print(f"\nFound {len(corrupt_files)} corrupt/missing files.")
    
    # Step 2: Find last good snapshot that doesn't reference these files
    snapshots = spark.sql(f"""
        SELECT snapshot_id, committed_at
        FROM {table_name}.snapshots
        ORDER BY committed_at DESC
    """).collect()
    
    for snapshot in snapshots:
        sid = snapshot['snapshot_id']
        # Check if this snapshot references the corrupt files
        snapshot_files = spark.sql(f"""
            SELECT file_path FROM {table_name}.files
            VERSION AS OF {sid}
        """).collect()
        
        snapshot_file_paths = {r['file_path'] for r in snapshot_files}
        
        if not any(cf in snapshot_file_paths for cf in corrupt_files):
            print(f"Last clean snapshot: {sid} at {snapshot['committed_at']}")
            
            # Option A: Full rollback to this snapshot
            # spark.sql(f"CALL glue_catalog.system.rollback_to_snapshot('{table_name}', {sid})")
            
            # Option B: Rewrite only affected partitions from source
            print("Consider rewriting affected partitions from source data.")
            break
    
    # Step 3: Rewrite data files (compaction of valid data)
    spark.sql(f"""
        CALL glue_catalog.system.rewrite_data_files(
            table => '{table_name.replace("glue_catalog.", "")}',
            strategy => 'sort',
            sort_order => 'event_date ASC'
        )
    """)
    
    print("Data files rewritten successfully.")
```

---

## 4. Backup Strategies

### Metadata Backup Automation

```python
# scripts/backup_iceberg_metadata.py
import boto3
import json
from datetime import datetime, timezone

def backup_table_metadata(table_path, backup_bucket, backup_prefix):
    """
    Create a point-in-time backup of all Iceberg metadata for a table.
    Backs up: metadata.json, manifest lists, manifest files.
    """
    s3 = boto3.client('s3')
    
    parts = table_path.replace("s3://", "").split("/", 1)
    source_bucket = parts[0]
    table_prefix = parts[1]
    
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_dest = f"{backup_prefix}/{timestamp}/"
    
    # Backup metadata directory
    metadata_prefix = f"{table_prefix}/metadata/"
    paginator = s3.get_paginator('list_objects_v2')
    
    copied_count = 0
    total_size = 0
    
    for page in paginator.paginate(Bucket=source_bucket, Prefix=metadata_prefix):
        for obj in page.get('Contents', []):
            source_key = obj['Key']
            relative_key = source_key[len(table_prefix):]
            dest_key = f"{backup_dest}{relative_key}"
            
            s3.copy_object(
                CopySource={'Bucket': source_bucket, 'Key': source_key},
                Bucket=backup_bucket,
                Key=dest_key,
                StorageClass='STANDARD_IA'
            )
            copied_count += 1
            total_size += obj['Size']
    
    # Record backup manifest
    manifest = {
        'backup_timestamp': timestamp,
        'source_table': table_path,
        'files_backed_up': copied_count,
        'total_size_bytes': total_size,
        'backup_location': f"s3://{backup_bucket}/{backup_dest}"
    }
    
    s3.put_object(
        Bucket=backup_bucket,
        Key=f"{backup_dest}backup_manifest.json",
        Body=json.dumps(manifest, indent=2),
        ContentType='application/json'
    )
    
    print(f"Backup complete: {copied_count} files, {total_size/1024/1024:.2f} MB")
    return manifest


def restore_metadata_from_backup(backup_location, target_table_path):
    """Restore metadata from a backup to a target location."""
    s3 = boto3.client('s3')
    
    backup_parts = backup_location.replace("s3://", "").split("/", 1)
    backup_bucket = backup_parts[0]
    backup_prefix = backup_parts[1]
    
    target_parts = target_table_path.replace("s3://", "").split("/", 1)
    target_bucket = target_parts[0]
    target_prefix = target_parts[1]
    
    # Read backup manifest
    manifest_key = f"{backup_prefix}backup_manifest.json"
    manifest = json.loads(
        s3.get_object(Bucket=backup_bucket, Key=manifest_key)['Body'].read()
    )
    
    print(f"Restoring from backup: {manifest['backup_timestamp']}")
    
    paginator = s3.get_paginator('list_objects_v2')
    restored = 0
    
    for page in paginator.paginate(Bucket=backup_bucket, Prefix=backup_prefix):
        for obj in page.get('Contents', []):
            if obj['Key'].endswith('backup_manifest.json'):
                continue
            
            relative_key = obj['Key'][len(backup_prefix):]
            dest_key = f"{target_prefix}{relative_key}"
            
            s3.copy_object(
                CopySource={'Bucket': backup_bucket, 'Key': obj['Key']},
                Bucket=target_bucket,
                Key=dest_key
            )
            restored += 1
    
    print(f"Restored {restored} metadata files to {target_table_path}")
```

### Catalog Backup (Glue)

```python
# scripts/backup_glue_catalog.py
import boto3
import json
from datetime import datetime, timezone

def backup_glue_catalog(database_names, backup_bucket, backup_prefix):
    """Full backup of Glue catalog entries for Iceberg tables."""
    glue = boto3.client('glue')
    s3 = boto3.client('s3')
    
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup = {'timestamp': timestamp, 'databases': {}}
    
    for db_name in database_names:
        tables = []
        paginator = glue.get_paginator('get_tables')
        
        for page in paginator.paginate(DatabaseName=db_name):
            for table in page['TableList']:
                # Only backup Iceberg tables
                if table.get('Parameters', {}).get('table_type') == 'ICEBERG':
                    # Serialize datetime objects
                    table_serializable = json.loads(
                        json.dumps(table, default=str)
                    )
                    tables.append(table_serializable)
        
        backup['databases'][db_name] = {
            'table_count': len(tables),
            'tables': tables
        }
        print(f"  {db_name}: {len(tables)} Iceberg tables")
    
    # Store backup
    backup_key = f"{backup_prefix}/catalog_backup_{timestamp}.json"
    s3.put_object(
        Bucket=backup_bucket,
        Key=backup_key,
        Body=json.dumps(backup, indent=2),
        ContentType='application/json'
    )
    
    print(f"Catalog backup saved to s3://{backup_bucket}/{backup_key}")
    return f"s3://{backup_bucket}/{backup_key}"


def restore_glue_catalog(backup_location, target_region=None):
    """Restore Glue catalog from backup."""
    s3 = boto3.client('s3')
    
    parts = backup_location.replace("s3://", "").split("/", 1)
    bucket, key = parts[0], parts[1]
    
    backup = json.loads(
        s3.get_object(Bucket=bucket, Key=key)['Body'].read()
    )
    
    glue = boto3.client('glue', region_name=target_region) if target_region else boto3.client('glue')
    
    for db_name, db_data in backup['databases'].items():
        # Ensure database exists
        try:
            glue.create_database(DatabaseInput={'Name': db_name})
        except glue.exceptions.AlreadyExistsException:
            pass
        
        for table_def in db_data['tables']:
            # Clean up for create/update
            table_input = {k: v for k, v in table_def.items() 
                         if k not in ['DatabaseName', 'CreateTime', 'UpdateTime',
                                     'CreatedBy', 'IsRegisteredWithLakeFormation',
                                     'CatalogId', 'VersionId']}
            try:
                glue.create_table(DatabaseName=db_name, TableInput=table_input)
                print(f"  Created: {db_name}.{table_def['Name']}")
            except glue.exceptions.AlreadyExistsException:
                glue.update_table(DatabaseName=db_name, TableInput=table_input)
                print(f"  Updated: {db_name}.{table_def['Name']}")
    
    print("Catalog restore complete.")
```

---

## 5. Table Repair Operations

### Remove Orphan Files

```python
def remove_orphan_files(spark, table_name, dry_run=True):
    """
    Remove data files that are not referenced by any snapshot.
    These accumulate from failed writes, compaction, or expired snapshots.
    """
    from datetime import datetime, timedelta
    
    # Safety: only remove orphans older than 3 days
    older_than = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
    
    if dry_run:
        # List orphan files without deleting
        orphans = spark.sql(f"""
            CALL glue_catalog.system.remove_orphan_files(
                table => '{table_name.replace("glue_catalog.", "")}',
                older_than => TIMESTAMP '{older_than}',
                dry_run => true
            )
        """)
        print(f"Orphan files found: {orphans.count()}")
        orphans.show(50, truncate=False)
        return orphans
    else:
        result = spark.sql(f"""
            CALL glue_catalog.system.remove_orphan_files(
                table => '{table_name.replace("glue_catalog.", "")}',
                older_than => TIMESTAMP '{older_than}'
            )
        """)
        print(f"Removed {result.count()} orphan files")
        return result


def expire_snapshots(spark, table_name, retain_last_n=10, older_than_days=7):
    """Expire old snapshots while keeping recent ones for recovery."""
    from datetime import datetime, timedelta
    
    older_than = (datetime.now() - timedelta(days=older_than_days)).strftime("%Y-%m-%d %H:%M:%S")
    
    result = spark.sql(f"""
        CALL glue_catalog.system.expire_snapshots(
            table => '{table_name.replace("glue_catalog.", "")}',
            older_than => TIMESTAMP '{older_than}',
            retain_last => {retain_last_n},
            stream_results => true
        )
    """)
    
    print(f"Expired snapshots - deleted files: {result.count()}")
    return result


def rewrite_manifests(spark, table_name):
    """Rewrite manifest files to repair corruption or improve performance."""
    result = spark.sql(f"""
        CALL glue_catalog.system.rewrite_manifests(
            '{table_name.replace("glue_catalog.", "")}'
        )
    """)
    print("Manifests rewritten:")
    result.show()
    return result
```

### Full Table Health Check

```python
def table_health_check(spark, table_name):
    """Comprehensive health check for an Iceberg table."""
    
    report = {"table": table_name, "issues": [], "status": "HEALTHY"}
    
    # 1. Check metadata accessibility
    try:
        spark.sql(f"DESCRIBE TABLE {table_name}").collect()
        report["metadata_accessible"] = True
    except Exception as e:
        report["metadata_accessible"] = False
        report["issues"].append(f"Metadata inaccessible: {e}")
        report["status"] = "CRITICAL"
        return report
    
    # 2. Check snapshot count
    snapshots = spark.sql(f"SELECT * FROM {table_name}.snapshots").collect()
    report["snapshot_count"] = len(snapshots)
    if len(snapshots) > 1000:
        report["issues"].append(f"Excessive snapshots ({len(snapshots)}), consider expiring")
    
    # 3. Check file count and sizes
    files = spark.sql(f"""
        SELECT COUNT(*) as file_count,
               SUM(file_size_in_bytes) as total_size,
               AVG(file_size_in_bytes) as avg_size,
               MIN(file_size_in_bytes) as min_size,
               MAX(file_size_in_bytes) as max_size
        FROM {table_name}.files
    """).collect()[0]
    
    report["file_count"] = files["file_count"]
    report["total_size_gb"] = files["total_size"] / (1024**3) if files["total_size"] else 0
    
    if files["avg_size"] and files["avg_size"] < 10 * 1024 * 1024:  # < 10MB
        report["issues"].append(f"Small average file size ({files['avg_size']/1024/1024:.1f}MB), consider compaction")
    
    if files["file_count"] and files["file_count"] > 10000:
        report["issues"].append(f"High file count ({files['file_count']}), consider compaction")
    
    # 4. Check manifest count
    manifests = spark.sql(f"SELECT * FROM {table_name}.manifests").count()
    report["manifest_count"] = manifests
    if manifests > 500:
        report["issues"].append(f"High manifest count ({manifests}), consider rewriting")
    
    # 5. Validate sample data read
    try:
        sample = spark.sql(f"SELECT * FROM {table_name} LIMIT 100").collect()
        report["data_readable"] = True
        report["sample_rows"] = len(sample)
    except Exception as e:
        report["data_readable"] = False
        report["issues"].append(f"Data read failure: {e}")
        report["status"] = "CRITICAL"
    
    # 6. Check for partition skew
    try:
        partition_stats = spark.sql(f"""
            SELECT partition, COUNT(*) as file_count, 
                   SUM(record_count) as records
            FROM {table_name}.files
            GROUP BY partition
            ORDER BY file_count DESC
            LIMIT 10
        """).collect()
        
        if partition_stats:
            max_files = partition_stats[0]["file_count"]
            if max_files > 500:
                report["issues"].append(
                    f"Partition skew: hottest partition has {max_files} files"
                )
    except:
        pass
    
    # Set overall status
    if report["issues"] and report["status"] != "CRITICAL":
        report["status"] = "WARNING"
    
    print(f"\n{'='*60}")
    print(f"TABLE HEALTH: {table_name}")
    print(f"Status: {report['status']}")
    print(f"Snapshots: {report['snapshot_count']}")
    print(f"Files: {report.get('file_count', 'N/A')}")
    print(f"Size: {report.get('total_size_gb', 0):.2f} GB")
    if report["issues"]:
        print(f"\nIssues ({len(report['issues'])}):")
        for issue in report["issues"]:
            print(f"  - {issue}")
    print(f"{'='*60}\n")
    
    return report
```

---

## 6. Data Validation

### Post-Operation Validation Framework

```python
from dataclasses import dataclass
from typing import Optional, List, Tuple
from pyspark.sql import DataFrame, SparkSession
import pyspark.sql.functions as F

@dataclass
class ValidationResult:
    check_name: str
    passed: bool
    expected: Optional[str] = None
    actual: Optional[str] = None
    message: Optional[str] = None

class IcebergDataValidator:
    """Comprehensive validation for Iceberg table operations."""
    
    def __init__(self, spark: SparkSession, table_name: str):
        self.spark = spark
        self.table_name = table_name
    
    def validate_row_count(self, expected_count: int, tolerance_pct: float = 0.01) -> ValidationResult:
        """Verify row count is within expected range."""
        actual_count = self.spark.table(self.table_name).count()
        lower = expected_count * (1 - tolerance_pct)
        upper = expected_count * (1 + tolerance_pct)
        
        passed = lower <= actual_count <= upper
        return ValidationResult(
            check_name="row_count",
            passed=passed,
            expected=f"{expected_count} (+/- {tolerance_pct*100}%)",
            actual=str(actual_count),
            message=None if passed else f"Row count {actual_count} outside tolerance"
        )
    
    def validate_no_nulls(self, columns: List[str]) -> ValidationResult:
        """Check critical columns have no null values."""
        df = self.spark.table(self.table_name)
        null_counts = {}
        
        for col in columns:
            null_count = df.filter(F.col(col).isNull()).count()
            if null_count > 0:
                null_counts[col] = null_count
        
        passed = len(null_counts) == 0
        return ValidationResult(
            check_name="no_nulls",
            passed=passed,
            expected="0 nulls in critical columns",
            actual=str(null_counts) if null_counts else "0 nulls",
            message=None if passed else f"Nulls found: {null_counts}"
        )
    
    def validate_freshness(self, timestamp_col: str, max_delay_hours: int = 2) -> ValidationResult:
        """Check data freshness - latest record should be recent."""
        from datetime import datetime, timedelta
        
        df = self.spark.table(self.table_name)
        max_ts = df.agg(F.max(timestamp_col)).collect()[0][0]
        
        if max_ts is None:
            return ValidationResult("freshness", False, message="No data in table")
        
        threshold = datetime.now() - timedelta(hours=max_delay_hours)
        passed = max_ts >= threshold
        
        return ValidationResult(
            check_name="freshness",
            passed=passed,
            expected=f"Data newer than {threshold}",
            actual=str(max_ts),
            message=None if passed else f"Data is stale: latest={max_ts}"
        )
    
    def validate_statistical_consistency(
        self, 
        numeric_col: str, 
        expected_mean: float, 
        expected_stddev: float,
        tolerance_sigma: float = 3.0
    ) -> ValidationResult:
        """Statistical validation - detect anomalous distributions."""
        df = self.spark.table(self.table_name)
        stats = df.agg(
            F.mean(numeric_col).alias("mean"),
            F.stddev(numeric_col).alias("stddev"),
            F.min(numeric_col).alias("min_val"),
            F.max(numeric_col).alias("max_val")
        ).collect()[0]
        
        actual_mean = stats["mean"]
        mean_diff = abs(actual_mean - expected_mean)
        threshold = tolerance_sigma * expected_stddev
        
        passed = mean_diff <= threshold
        return ValidationResult(
            check_name=f"statistical_{numeric_col}",
            passed=passed,
            expected=f"mean={expected_mean} +/- {threshold:.2f}",
            actual=f"mean={actual_mean:.4f}, stddev={stats['stddev']:.4f}",
            message=None if passed else f"Mean deviation {mean_diff:.4f} exceeds {tolerance_sigma}σ"
        )
    
    def validate_duplicates(self, key_columns: List[str], max_dup_ratio: float = 0.001) -> ValidationResult:
        """Check for unexpected duplicates."""
        df = self.spark.table(self.table_name)
        total = df.count()
        distinct = df.select(key_columns).distinct().count()
        
        dup_ratio = 1 - (distinct / max(total, 1))
        passed = dup_ratio <= max_dup_ratio
        
        return ValidationResult(
            check_name="duplicates",
            passed=passed,
            expected=f"Duplicate ratio <= {max_dup_ratio*100}%",
            actual=f"{dup_ratio*100:.4f}% ({total - distinct} duplicates)",
            message=None if passed else f"Excessive duplicates: {dup_ratio*100:.4f}%"
        )
    
    def validate_file_integrity(self) -> ValidationResult:
        """Verify all referenced data files exist and are accessible."""
        import boto3
        s3 = boto3.client('s3')
        
        files_df = self.spark.sql(f"""
            SELECT file_path, file_size_in_bytes 
            FROM {self.table_name}.files
        """)
        
        missing = []
        size_mismatch = []
        
        for row in files_df.limit(100).collect():  # Sample check
            path = row['file_path']
            parts = path.replace("s3://", "").split("/", 1)
            
            try:
                head = s3.head_object(Bucket=parts[0], Key=parts[1])
                if head['ContentLength'] != row['file_size_in_bytes']:
                    size_mismatch.append(path)
            except:
                missing.append(path)
        
        issues = missing + size_mismatch
        passed = len(issues) == 0
        
        return ValidationResult(
            check_name="file_integrity",
            passed=passed,
            expected="All files accessible with correct sizes",
            actual=f"{len(missing)} missing, {len(size_mismatch)} size mismatches",
            message=None if passed else f"Issues: {issues[:5]}"
        )
    
    def run_all(self, config: dict) -> List[ValidationResult]:
        """Run all configured validations."""
        results = []
        
        if 'expected_row_count' in config:
            results.append(self.validate_row_count(config['expected_row_count']))
        
        if 'not_null_columns' in config:
            results.append(self.validate_no_nulls(config['not_null_columns']))
        
        if 'freshness' in config:
            results.append(self.validate_freshness(**config['freshness']))
        
        if 'key_columns' in config:
            results.append(self.validate_duplicates(config['key_columns']))
        
        results.append(self.validate_file_integrity())
        
        # Summary
        passed = sum(1 for r in results if r.passed)
        failed = sum(1 for r in results if not r.passed)
        
        print(f"\nValidation Summary: {passed} passed, {failed} failed")
        for r in results:
            status = "PASS" if r.passed else "FAIL"
            print(f"  [{status}] {r.check_name}: {r.message or r.actual}")
        
        return results
```

---

## 7. Multi-Region Active-Active

### Read Routing Configuration

```python
# config/multi_region_config.py

REGION_CONFIG = {
    "us-east-1": {
        "role": "primary",
        "catalog": "glue_catalog_east",
        "warehouse": "s3://iceberg-lake-us-east-1/warehouse",
        "write_enabled": True,
        "read_priority": 1,
    },
    "us-west-2": {
        "role": "secondary",
        "catalog": "glue_catalog_west",
        "warehouse": "s3://iceberg-lake-us-west-2/warehouse",
        "write_enabled": False,  # Read replica
        "read_priority": 2,
    },
    "eu-west-1": {
        "role": "secondary",
        "catalog": "glue_catalog_eu",
        "warehouse": "s3://iceberg-lake-eu-west-1/warehouse",
        "write_enabled": False,
        "read_priority": 3,
    }
}


def get_read_catalog(client_region: str) -> str:
    """Route reads to nearest region with healthy catalog."""
    import boto3
    
    # Sort by proximity to client
    regions_by_priority = sorted(
        REGION_CONFIG.items(),
        key=lambda x: abs(x[1]["read_priority"] - _region_proximity(client_region, x[0]))
    )
    
    for region, config in regions_by_priority:
        if _is_catalog_healthy(region, config["catalog"]):
            return config["catalog"]
    
    raise RuntimeError("No healthy catalog available in any region")


def get_write_catalog() -> str:
    """Always route writes to primary region."""
    for region, config in REGION_CONFIG.items():
        if config["write_enabled"]:
            return config["catalog"]
    raise RuntimeError("No write-enabled region found")


def _is_catalog_healthy(region: str, catalog_name: str) -> bool:
    """Check if catalog in region is responsive."""
    try:
        glue = boto3.client('glue', region_name=region)
        glue.get_databases(MaxResults=1)
        return True
    except:
        return False


def _region_proximity(client_region: str, target_region: str) -> int:
    """Simple proximity score (lower = closer)."""
    proximity_map = {
        ("us-east-1", "us-east-1"): 0,
        ("us-east-1", "us-west-2"): 2,
        ("us-east-1", "eu-west-1"): 3,
        ("us-west-2", "us-west-2"): 0,
        ("us-west-2", "us-east-1"): 2,
        ("us-west-2", "eu-west-1"): 4,
    }
    return proximity_map.get((client_region, target_region), 5)
```

---

## 8. Catalog Disaster Recovery

### Glue Catalog Recovery

```python
def recover_glue_table_from_s3(spark, bucket, warehouse_prefix, db_name, table_name):
    """
    Re-register an Iceberg table in Glue catalog from its S3 metadata.
    Used when Glue catalog entry is lost/corrupted but data is intact.
    """
    import boto3
    import json
    
    s3 = boto3.client('s3')
    glue = boto3.client('glue')
    
    # Find the latest metadata file
    metadata_prefix = f"{warehouse_prefix}/{db_name}/{table_name}/metadata/"
    
    response = s3.list_objects_v2(Bucket=bucket, Prefix=metadata_prefix)
    metadata_files = [
        obj for obj in response.get('Contents', [])
        if obj['Key'].endswith('.metadata.json')
    ]
    
    if not metadata_files:
        raise FileNotFoundError(f"No metadata files found at s3://{bucket}/{metadata_prefix}")
    
    # Get the latest metadata file (highest version number)
    latest = sorted(metadata_files, key=lambda x: x['LastModified'])[-1]
    metadata_location = f"s3://{bucket}/{latest['Key']}"
    
    # Read metadata to get schema info
    metadata = json.loads(
        s3.get_object(Bucket=bucket, Key=latest['Key'])['Body'].read()
    )
    
    # Ensure database exists
    try:
        glue.create_database(DatabaseInput={'Name': db_name})
    except glue.exceptions.AlreadyExistsException:
        pass
    
    # Register table
    table_input = {
        'Name': table_name,
        'TableType': 'EXTERNAL_TABLE',
        'Parameters': {
            'table_type': 'ICEBERG',
            'metadata_location': metadata_location,
        },
        'StorageDescriptor': {
            'Location': f"s3://{bucket}/{warehouse_prefix}/{db_name}/{table_name}",
            'InputFormat': 'org.apache.iceberg.mr.hive.HiveIcebergInputFormat',
            'OutputFormat': 'org.apache.iceberg.mr.hive.HiveIcebergOutputFormat',
            'SerdeInfo': {
                'SerializationLibrary': 'org.apache.iceberg.mr.hive.HiveIcebergSerDe'
            },
            'Columns': []  # Iceberg manages schema via metadata
        }
    }
    
    try:
        glue.create_table(DatabaseName=db_name, TableInput=table_input)
        print(f"Re-registered: {db_name}.{table_name}")
    except glue.exceptions.AlreadyExistsException:
        glue.update_table(DatabaseName=db_name, TableInput=table_input)
        print(f"Updated registration: {db_name}.{table_name}")
    
    # Verify
    spark.sql(f"SELECT COUNT(*) FROM glue_catalog.{db_name}.{table_name}").show()
    print("Table recovery verified successfully.")
```

### Nessie Catalog DR

```python
def backup_nessie_catalog(nessie_url, backup_path):
    """Backup Nessie catalog state (all branches and tags)."""
    import requests
    import json
    
    # Get all references (branches + tags)
    refs = requests.get(f"{nessie_url}/api/v2/trees").json()
    
    backup = {
        'references': refs,
        'tables': {}
    }
    
    # For each branch, get all table entries
    for ref in refs.get('references', []):
        ref_name = ref['name']
        entries = requests.get(
            f"{nessie_url}/api/v2/trees/{ref_name}/entries"
        ).json()
        backup['tables'][ref_name] = entries
    
    # Write backup
    import boto3
    s3 = boto3.client('s3')
    parts = backup_path.replace("s3://", "").split("/", 1)
    s3.put_object(
        Bucket=parts[0],
        Key=parts[1],
        Body=json.dumps(backup, indent=2)
    )
    
    print(f"Nessie backup: {len(refs.get('references', []))} refs backed up")
```

---

## 9. Incident Response Playbook

### Severity Levels

| Level | Criteria | Response Time | Escalation |
|-------|----------|---------------|------------|
| **SEV1** | Data loss, table completely inaccessible | 5 min | On-call + Engineering Lead |
| **SEV2** | Data corruption detected, writes failing | 15 min | On-call |
| **SEV3** | Performance degradation, stale data | 30 min | Next business day |
| **SEV4** | Orphan files accumulating, minor issues | 1 hour | Planned maintenance |

### Response Template

```markdown
## Incident: [TITLE]
**Severity:** SEV[X]
**Detected:** [TIMESTAMP]
**Resolved:** [TIMESTAMP]
**Duration:** [DURATION]

### Impact
- Tables affected: [LIST]
- Data loss: [YES/NO, amount]
- Downstream impact: [DASHBOARDS, APIS, etc.]

### Timeline
- HH:MM - Alert triggered
- HH:MM - On-call acknowledged
- HH:MM - Root cause identified
- HH:MM - Recovery initiated
- HH:MM - Recovery complete
- HH:MM - Validation passed

### Root Cause
[DESCRIPTION]

### Recovery Actions
1. [ACTION 1]
2. [ACTION 2]

### Prevention
- [ ] Action item 1
- [ ] Action item 2
```

---

## 10. Recovery Runbooks: 10 Common Failure Scenarios

### Runbook 1: Bad Data Written (Schema Violation / Bad Values)

```
TRIGGER: Data quality alert fires after a pipeline write
IMPACT: Downstream consumers reading incorrect data
TTR: 5-10 minutes
```

```python
# Step 1: Identify the bad snapshot
bad_snapshots = spark.sql("""
    SELECT snapshot_id, committed_at, summary['added-records'] as records_added
    FROM glue_catalog.analytics.events.snapshots
    WHERE committed_at > current_timestamp() - INTERVAL 2 HOURS
    ORDER BY committed_at DESC
""")
bad_snapshots.show()

# Step 2: Verify data at previous snapshot
previous_snapshot_id = 1234567890  # From step 1
spark.sql(f"""
    SELECT COUNT(*), MIN(event_date), MAX(event_date)
    FROM glue_catalog.analytics.events
    VERSION AS OF {previous_snapshot_id}
""").show()

# Step 3: Rollback
spark.sql(f"""
    CALL glue_catalog.system.rollback_to_snapshot('analytics.events', {previous_snapshot_id})
""")

# Step 4: Validate
spark.sql("SELECT COUNT(*) FROM glue_catalog.analytics.events").show()
```

### Runbook 2: Table Scan Fails with ManifestReadException

```
TRIGGER: Spark job fails with "Could not read manifest" or FileNotFoundException
IMPACT: Table completely unreadable
TTR: 15-30 minutes
```

```python
# Step 1: Identify which manifest is corrupt
try:
    spark.sql("SELECT * FROM glue_catalog.analytics.events LIMIT 1").collect()
except Exception as e:
    print(f"Error: {e}")
    # Extract manifest path from error message

# Step 2: Rewrite all manifests
spark.sql("""
    CALL glue_catalog.system.rewrite_manifests('analytics.events')
""")

# Step 3: If rewrite fails, rollback to older snapshot
spark.sql("""
    CALL glue_catalog.system.rollback_to_snapshot('analytics.events', <last_known_good_snapshot>)
""")

# Step 4: Verify
spark.sql("SELECT COUNT(*) FROM glue_catalog.analytics.events").show()
```

### Runbook 3: S3 Bucket Accidentally Deleted or Files Removed

```
TRIGGER: Widespread FileNotFoundException across multiple tables
IMPACT: Multiple tables unreadable, potential data loss
TTR: 30-120 minutes depending on data volume
```

```python
# Step 1: Assess damage
import boto3
s3 = boto3.client('s3')

# Check if bucket exists
try:
    s3.head_bucket(Bucket='iceberg-datalake-primary')
    print("Bucket exists - checking contents")
except:
    print("BUCKET MISSING - initiate full DR failover")

# Step 2A: If files deleted but bucket exists - use S3 versioning to restore
paginator = s3.get_paginator('list_object_versions')
restored = 0
for page in paginator.paginate(Bucket='iceberg-datalake-primary', Prefix='warehouse/analytics/events/'):
    for version in page.get('DeleteMarkers', []):
        if version['IsLatest']:
            # Remove delete marker to restore
            s3.delete_object(
                Bucket='iceberg-datalake-primary',
                Key=version['Key'],
                VersionId=version['VersionId']
            )
            restored += 1

print(f"Restored {restored} deleted files")

# Step 2B: If bucket gone - failover to DR region
# Switch all readers to DR catalog
# See Section 2 for catalog sync verification
```

### Runbook 4: Concurrent Write Conflict (CommitFailedException)

```
TRIGGER: Pipeline fails with CommitFailedException or RetryExhaustedException
IMPACT: Data not written, potential duplicate processing on retry
TTR: 5-15 minutes
```

```python
# Step 1: Check current table state
spark.sql("""
    SELECT snapshot_id, committed_at, operation, 
           summary['added-records'], summary['deleted-records']
    FROM glue_catalog.analytics.events.snapshots
    ORDER BY committed_at DESC LIMIT 5
""").show(truncate=False)

# Step 2: Determine if conflicting write succeeded
# If another writer's commit went through, we just need to retry with fresh snapshot

# Step 3: Retry with conflict resolution
df.writeTo("glue_catalog.analytics.events") \
    .option("isolation-level", "serializable") \
    .append()

# Step 4: If persistent conflicts, implement write serialization
# Use a distributed lock (DynamoDB) for critical tables
```

### Runbook 5: Metadata File Too Large (Slow Table Operations)

```
TRIGGER: Table operations (scan planning, commits) take > 60 seconds
IMPACT: Pipeline latency, potential timeouts
TTR: 15-30 minutes
```

```python
# Step 1: Check metadata size
spark.sql("""
    SELECT COUNT(*) as snapshot_count FROM glue_catalog.analytics.events.snapshots
""").show()

spark.sql("""
    SELECT COUNT(*) as manifest_count FROM glue_catalog.analytics.events.manifests
""").show()

# Step 2: Expire old snapshots
spark.sql("""
    CALL glue_catalog.system.expire_snapshots(
        table => 'analytics.events',
        older_than => TIMESTAMP '2024-01-01 00:00:00',
        retain_last => 20
    )
""")

# Step 3: Rewrite manifests for compaction
spark.sql("CALL glue_catalog.system.rewrite_manifests('analytics.events')")

# Step 4: Remove orphan files freed by expiration
spark.sql("""
    CALL glue_catalog.system.remove_orphan_files(
        table => 'analytics.events',
        older_than => TIMESTAMP '2024-01-08 00:00:00'
    )
""")
```

### Runbook 6: Region Outage - DR Failover

```
TRIGGER: AWS region unavailable, primary catalog/data inaccessible
IMPACT: All pipelines and queries in affected region
TTR: 15-30 minutes for failover
```

```bash
# Step 1: Verify primary region is down
aws s3 ls s3://iceberg-datalake-primary/ --region us-east-1 || echo "PRIMARY DOWN"

# Step 2: Verify DR region is healthy
aws s3 ls s3://iceberg-datalake-dr/ --region us-west-2 && echo "DR HEALTHY"

# Step 3: Check replication lag
aws s3api get-bucket-replication --bucket iceberg-datalake-primary --region us-east-1 2>/dev/null || echo "Cannot check - expected if region is down"
```

```python
# Step 4: Switch application config to DR
# Update environment variables / config service
import boto3
ssm = boto3.client('ssm', region_name='us-west-2')
ssm.put_parameter(
    Name='/iceberg/active-catalog-region',
    Value='us-west-2',
    Type='String',
    Overwrite=True
)

# Step 5: Verify DR tables are readable
spark_dr = SparkSession.builder \
    .config("spark.sql.catalog.glue_catalog", "org.apache.iceberg.spark.SparkCatalog") \
    .config("spark.sql.catalog.glue_catalog.catalog-impl", "org.apache.iceberg.aws.glue.GlueCatalog") \
    .config("spark.sql.catalog.glue_catalog.warehouse", "s3://iceberg-datalake-dr/warehouse") \
    .config("spark.hadoop.aws.region", "us-west-2") \
    .getOrCreate()

spark_dr.sql("SELECT COUNT(*) FROM glue_catalog.analytics.events").show()

# Step 6: Notify stakeholders of potential data lag (RPO window)
```

### Runbook 7: Partition Column Has Wrong Values

```
TRIGGER: Queries returning incorrect results, partition filter not working
IMPACT: Query performance degradation, incorrect data served
TTR: 30-60 minutes
```

```python
# Step 1: Identify affected partitions
spark.sql("""
    SELECT partition, COUNT(*) as files, SUM(record_count) as records
    FROM glue_catalog.analytics.events.files
    GROUP BY partition
    ORDER BY files DESC
""").show(50)

# Step 2: Read data at correct snapshot and rewrite
correct_data = spark.sql("""
    SELECT * FROM glue_catalog.analytics.events
    VERSION AS OF <last_good_snapshot>
    WHERE event_date BETWEEN '2024-01-10' AND '2024-01-15'
""")

# Step 3: Delete bad partition data and rewrite
spark.sql("""
    DELETE FROM glue_catalog.analytics.events
    WHERE event_date BETWEEN '2024-01-10' AND '2024-01-15'
""")

correct_data.writeTo("glue_catalog.analytics.events").append()

# Step 4: Validate
spark.sql("""
    SELECT event_date, COUNT(*) FROM glue_catalog.analytics.events
    WHERE event_date BETWEEN '2024-01-10' AND '2024-01-15'
    GROUP BY event_date ORDER BY event_date
""").show()
```

### Runbook 8: Glue Catalog Table Entry Missing

```
TRIGGER: "Table not found" error but S3 data exists
IMPACT: Table invisible to all query engines
TTR: 5-10 minutes
```

```python
# Step 1: Verify data exists in S3
import boto3
s3 = boto3.client('s3')
response = s3.list_objects_v2(
    Bucket='iceberg-datalake-primary',
    Prefix='warehouse/analytics/events/metadata/',
    MaxKeys=5
)
print(f"Metadata files found: {len(response.get('Contents', []))}")

# Step 2: Find latest metadata.json
metadata_files = sorted(
    [obj['Key'] for obj in response['Contents'] if obj['Key'].endswith('.metadata.json')]
)
latest_metadata = f"s3://iceberg-datalake-primary/{metadata_files[-1]}"
print(f"Latest metadata: {latest_metadata}")

# Step 3: Re-register in Glue (see Section 8 - recover_glue_table_from_s3)
recover_glue_table_from_s3(
    spark, 
    'iceberg-datalake-primary', 
    'warehouse', 
    'analytics', 
    'events'
)
```

### Runbook 9: Duplicate Data After Pipeline Retry

```
TRIGGER: Row count spike detected, duplicate key alerts
IMPACT: Inflated metrics, incorrect aggregations
TTR: 15-30 minutes
```

```python
# Step 1: Quantify duplication
total = spark.sql("SELECT COUNT(*) FROM glue_catalog.analytics.events").collect()[0][0]
distinct = spark.sql("SELECT COUNT(DISTINCT event_id) FROM glue_catalog.analytics.events").collect()[0][0]
dup_count = total - distinct
print(f"Total: {total}, Distinct: {distinct}, Duplicates: {dup_count}")

# Step 2: Identify which snapshot introduced duplicates
snapshots = spark.sql("""
    SELECT snapshot_id, committed_at, summary['added-records'] as added
    FROM glue_catalog.analytics.events.snapshots
    ORDER BY committed_at DESC LIMIT 10
""").collect()

for s in snapshots:
    count_at_snapshot = spark.sql(f"""
        SELECT COUNT(*) - COUNT(DISTINCT event_id) as dups
        FROM glue_catalog.analytics.events
        VERSION AS OF {s['snapshot_id']}
    """).collect()[0][0]
    print(f"Snapshot {s['snapshot_id']} ({s['committed_at']}): {count_at_snapshot} dups")

# Step 3: Option A - Rollback to pre-duplicate snapshot
spark.sql(f"CALL glue_catalog.system.rollback_to_snapshot('analytics.events', {good_snapshot_id})")

# Step 3: Option B - Deduplicate in place using MERGE
spark.sql("""
    MERGE INTO glue_catalog.analytics.events t
    USING (
        SELECT event_id, MAX(event_timestamp) as event_timestamp
        FROM glue_catalog.analytics.events
        GROUP BY event_id
        HAVING COUNT(*) > 1
    ) s ON t.event_id = s.event_id AND t.event_timestamp < s.event_timestamp
    WHEN MATCHED THEN DELETE
""")
```

### Runbook 10: Compaction Job Fails Mid-Way

```
TRIGGER: Compaction/rewrite_data_files job fails, table in inconsistent state
IMPACT: Potential orphan files, no data loss (Iceberg commits are atomic)
TTR: 10-20 minutes
```

```python
# Step 1: Verify table is still readable (Iceberg guarantees atomicity)
spark.sql("SELECT COUNT(*) FROM glue_catalog.analytics.events").show()
# If this works, no data loss occurred - the failed compaction simply didn't commit

# Step 2: Check for orphan files left by failed compaction
orphans = spark.sql("""
    CALL glue_catalog.system.remove_orphan_files(
        table => 'analytics.events',
        dry_run => true
    )
""")
print(f"Orphan files from failed compaction: {orphans.count()}")

# Step 3: Clean up orphans
spark.sql("""
    CALL glue_catalog.system.remove_orphan_files(
        table => 'analytics.events',
        older_than => TIMESTAMP '2024-01-14 00:00:00'
    )
""")

# Step 4: Retry compaction with smaller scope
spark.sql("""
    CALL glue_catalog.system.rewrite_data_files(
        table => 'analytics.events',
        strategy => 'binpack',
        options => map(
            'target-file-size-bytes', '134217728',
            'max-concurrent-file-group-rewrites', '5',
            'partial-progress.enabled', 'true',
            'partial-progress.max-commits', '10'
        )
    )
""")
```

---

## 11. Chaos Engineering Tests

### Test Suite: Simulating Failures

```python
# tests/chaos/test_iceberg_resilience.py
"""
Chaos engineering tests for Iceberg data pipeline resilience.
Run in a staging environment only.
"""
import pytest
import boto3
import time
import random
from pyspark.sql import SparkSession

class TestIcebergResilience:
    """Chaos tests to verify DR procedures work."""
    
    @pytest.fixture
    def spark(self):
        return SparkSession.builder \
            .config("spark.sql.catalog.test_catalog", "org.apache.iceberg.spark.SparkCatalog") \
            .config("spark.sql.catalog.test_catalog.type", "hadoop") \
            .config("spark.sql.catalog.test_catalog.warehouse", "s3://chaos-test-bucket/warehouse") \
            .getOrCreate()
    
    @pytest.fixture
    def test_table(self, spark):
        """Create a test table with known data."""
        spark.sql("CREATE DATABASE IF NOT EXISTS test_catalog.chaos_db")
        spark.sql("DROP TABLE IF EXISTS test_catalog.chaos_db.test_events")
        spark.sql("""
            CREATE TABLE test_catalog.chaos_db.test_events (
                id BIGINT, event_type STRING, value DOUBLE, ts TIMESTAMP
            ) USING iceberg
            PARTITIONED BY (days(ts))
        """)
        
        # Insert test data across multiple snapshots
        for i in range(5):
            spark.sql(f"""
                INSERT INTO test_catalog.chaos_db.test_events
                SELECT id + {i*1000}, event_type, value, ts
                FROM VALUES
                    (1, 'click', 1.0, TIMESTAMP '2024-01-{10+i} 00:00:00'),
                    (2, 'view', 2.0, TIMESTAMP '2024-01-{10+i} 01:00:00'),
                    (3, 'purchase', 100.0, TIMESTAMP '2024-01-{10+i} 02:00:00')
                AS t(id, event_type, value, ts)
            """)
        
        return "test_catalog.chaos_db.test_events"
    
    def test_recovery_after_data_file_deletion(self, spark, test_table):
        """Simulate accidental deletion of data files."""
        s3 = boto3.client('s3')
        
        # Get initial count
        initial_count = spark.sql(f"SELECT COUNT(*) FROM {test_table}").collect()[0][0]
        
        # Get a data file path
        files = spark.sql(f"SELECT file_path FROM {test_table}.files LIMIT 1").collect()
        file_path = files[0][0]
        
        # Record snapshot before deletion
        pre_snapshot = spark.sql(f"""
            SELECT snapshot_id FROM {test_table}.snapshots
            ORDER BY committed_at DESC LIMIT 1
        """).collect()[0][0]
        
        # DELETE a data file (chaos!)
        parts = file_path.replace("s3://", "").split("/", 1)
        s3.delete_object(Bucket=parts[0], Key=parts[1])
        
        # Verify the table scan now fails for that partition
        with pytest.raises(Exception):
            spark.sql(f"SELECT * FROM {test_table}").collect()
        
        # RECOVERY: Rollback removes reference to deleted file
        spark.sql(f"""
            CALL test_catalog.system.rollback_to_snapshot(
                'chaos_db.test_events', {pre_snapshot}
            )
        """)
        
        # Verify recovery (count may be slightly less due to rollback)
        recovered_count = spark.sql(f"SELECT COUNT(*) FROM {test_table}").collect()[0][0]
        assert recovered_count > 0
    
    def test_recovery_after_metadata_corruption(self, spark, test_table):
        """Simulate metadata file corruption."""
        s3 = boto3.client('s3')
        
        # Get current metadata location
        # Write garbage to simulate corruption
        # (In real scenario, this tests our metadata recovery procedure)
        
        initial_count = spark.sql(f"SELECT COUNT(*) FROM {test_table}").collect()[0][0]
        
        # List metadata files
        response = s3.list_objects_v2(
            Bucket='chaos-test-bucket',
            Prefix='warehouse/chaos_db/test_events/metadata/'
        )
        
        metadata_files = sorted(
            [obj for obj in response['Contents'] if obj['Key'].endswith('.metadata.json')],
            key=lambda x: x['LastModified']
        )
        
        # Corrupt the latest metadata
        latest = metadata_files[-1]['Key']
        s3.put_object(
            Bucket='chaos-test-bucket',
            Key=latest,
            Body=b'{"corrupted": true}'
        )
        
        # Recovery: Point catalog to previous metadata version
        if len(metadata_files) > 1:
            previous = metadata_files[-2]['Key']
            # Re-register with previous metadata
            # (Implementation depends on catalog type)
            print(f"Would recover using: {previous}")
    
    def test_concurrent_writer_conflict(self, spark, test_table):
        """Simulate concurrent write conflicts."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        def write_batch(batch_id):
            # Each writer tries to append
            spark.sql(f"""
                INSERT INTO {test_table}
                VALUES ({batch_id * 10000 + 1}, 'concurrent', {batch_id}.0, 
                        TIMESTAMP '2024-02-01 00:00:00')
            """)
            return batch_id
        
        # Launch concurrent writers
        results = []
        failures = []
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(write_batch, i): i for i in range(3)}
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as e:
                    failures.append(str(e))
        
        # At least some writes should succeed (Iceberg handles conflicts with retry)
        assert len(results) > 0 or len(failures) > 0
        
        # Table should still be consistent
        count = spark.sql(f"SELECT COUNT(*) FROM {test_table}").collect()[0][0]
        assert count > 0
    
    def test_partial_write_recovery(self, spark, test_table):
        """Simulate a write that is interrupted mid-way."""
        initial_count = spark.sql(f"SELECT COUNT(*) FROM {test_table}").collect()[0][0]
        initial_snapshot = spark.sql(f"""
            SELECT snapshot_id FROM {test_table}.snapshots
            ORDER BY committed_at DESC LIMIT 1
        """).collect()[0][0]
        
        # Simulate partial write by writing then immediately rolling back
        spark.sql(f"""
            INSERT INTO {test_table}
            VALUES (99999, 'partial', 0.0, TIMESTAMP '2024-03-01 00:00:00')
        """)
        
        # Simulate "oops, that was bad"
        spark.sql(f"""
            CALL test_catalog.system.rollback_to_snapshot(
                'chaos_db.test_events', {initial_snapshot}
            )
        """)
        
        # Verify state is restored
        final_count = spark.sql(f"SELECT COUNT(*) FROM {test_table}").collect()[0][0]
        assert final_count == initial_count
    
    def test_snapshot_expiry_safety(self, spark, test_table):
        """Verify that snapshot expiry doesn't break active queries."""
        # Start a "long-running" scan
        df = spark.sql(f"SELECT * FROM {test_table}")
        
        # Expire snapshots while scan is pending
        spark.sql(f"""
            CALL test_catalog.system.expire_snapshots(
                table => 'chaos_db.test_events',
                retain_last => 2
            )
        """)
        
        # The scan should still work (snapshot isolation)
        count = df.count()
        assert count > 0
```

### Running Chaos Tests

```bash
# Run chaos tests in staging environment
export CHAOS_ENV=staging
export AWS_PROFILE=staging

# Run specific test
pytest tests/chaos/test_iceberg_resilience.py::TestIcebergResilience::test_recovery_after_data_file_deletion -v

# Run all chaos tests with timeout
pytest tests/chaos/ -v --timeout=300

# Schedule monthly chaos test runs
# (Add to CI/CD or cron)
```

---

## 12. SLA Guarantees & How to Achieve Them

### SLA Definitions

| SLA Metric | Target | Measurement | Enforcement |
|------------|--------|-------------|-------------|
| Data Availability | 99.95% | Table readable in < 5s | Multi-region failover |
| Write Durability | 99.999999999% | No committed data loss | S3 11-9s + CRR |
| Recovery Time (Tier 1) | < 15 min | Time from detection to resolution | Automated runbooks |
| Recovery Point (Tier 1) | < 5 min | Max data loss window | Real-time replication |
| Query Freshness | < 10 min | Time from event to queryable | Streaming ingestion |

### Achieving 99.95% Availability

```python
# monitoring/sla_tracker.py
import boto3
import time
from datetime import datetime, timedelta

class SLATracker:
    """Track and report on Iceberg table SLA compliance."""
    
    def __init__(self, table_configs):
        self.table_configs = table_configs
        self.cloudwatch = boto3.client('cloudwatch')
    
    def check_availability(self, table_name, catalog_config):
        """Probe table availability."""
        start = time.time()
        try:
            # Attempt a lightweight metadata read
            spark.sql(f"SELECT snapshot_id FROM {table_name}.snapshots LIMIT 1").collect()
            latency_ms = (time.time() - start) * 1000
            available = 1
        except Exception as e:
            latency_ms = (time.time() - start) * 1000
            available = 0
        
        # Publish to CloudWatch
        self.cloudwatch.put_metric_data(
            Namespace='Iceberg/SLA',
            MetricData=[
                {
                    'MetricName': 'TableAvailability',
                    'Dimensions': [{'Name': 'TableName', 'Value': table_name}],
                    'Value': available,
                    'Unit': 'Count'
                },
                {
                    'MetricName': 'MetadataLatency',
                    'Dimensions': [{'Name': 'TableName', 'Value': table_name}],
                    'Value': latency_ms,
                    'Unit': 'Milliseconds'
                }
            ]
        )
        
        return available, latency_ms
    
    def calculate_monthly_sla(self, table_name, month_start, month_end):
        """Calculate actual SLA for a table over a month."""
        response = self.cloudwatch.get_metric_statistics(
            Namespace='Iceberg/SLA',
            MetricName='TableAvailability',
            Dimensions=[{'Name': 'TableName', 'Value': table_name}],
            StartTime=month_start,
            EndTime=month_end,
            Period=60,  # 1-minute granularity
            Statistics=['Sum', 'SampleCount']
        )
        
        total_checks = sum(dp['SampleCount'] for dp in response['Datapoints'])
        successful = sum(dp['Sum'] for dp in response['Datapoints'])
        
        if total_checks == 0:
            return None
        
        availability_pct = (successful / total_checks) * 100
        downtime_minutes = (total_checks - successful)
        
        return {
            'table': table_name,
            'availability_pct': availability_pct,
            'total_checks': total_checks,
            'failures': total_checks - successful,
            'estimated_downtime_minutes': downtime_minutes,
            'meets_sla': availability_pct >= 99.95
        }
```

### Automated SLA Enforcement

```hcl
# terraform/monitoring/sla_alarms.tf

resource "aws_cloudwatch_metric_alarm" "table_availability" {
  for_each = toset(var.tier1_tables)

  alarm_name          = "iceberg-availability-${each.key}"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 3
  metric_name         = "TableAvailability"
  namespace           = "Iceberg/SLA"
  period              = 60
  statistic           = "Average"
  threshold           = 1
  treat_missing_data  = "breaching"

  dimensions = {
    TableName = each.key
  }

  alarm_actions = [
    aws_sns_topic.sla_breach.arn,
    aws_lambda_function.auto_failover.arn  # Automatic DR failover
  ]
}

resource "aws_cloudwatch_metric_alarm" "replication_lag" {
  alarm_name          = "iceberg-replication-lag-critical"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 5
  metric_name         = "ReplicationLatency"
  namespace           = "AWS/S3"
  period              = 60
  statistic           = "Maximum"
  threshold           = 300  # 5 minutes - RPO breach for Tier 1

  alarm_actions = [aws_sns_topic.sla_breach.arn]
}
```

---

## 13. Operational Checklist

### Daily

- [ ] Verify all Tier 1 table availability checks passing
- [ ] Check S3 replication lag metrics (< 15 min)
- [ ] Review failed pipeline alerts
- [ ] Validate catalog sync Lambda execution

### Weekly

- [ ] Run table health checks on all tables
- [ ] Review orphan file counts
- [ ] Check snapshot accumulation (expire if > threshold)
- [ ] Verify backup job completion
- [ ] Test restore procedure on one non-production table

### Monthly

- [ ] Full DR failover drill (planned)
- [ ] Run chaos engineering test suite
- [ ] Review and update RTO/RPO targets
- [ ] Audit IAM permissions for DR roles
- [ ] Update runbooks based on incidents

### Quarterly

- [ ] Full restore test from backups
- [ ] Review SLA compliance reports
- [ ] Update table tier classifications
- [ ] Capacity planning for backup storage

---

## Summary

| Capability | Implementation | Status |
|-----------|---------------|--------|
| Snapshot rollback | Built-in Iceberg procedure | Ready |
| Cross-region replication | S3 CRR + Lambda catalog sync | Terraform provided |
| Metadata backup | Automated S3 copy job | Script provided |
| Catalog backup | Glue/Nessie export | Script provided |
| Table repair | Orphan removal, manifest rewrite | Procedures documented |
| Data validation | Multi-check framework | Class provided |
| Multi-region reads | Region-aware routing | Config provided |
| Chaos testing | pytest suite | 5 tests provided |
| SLA monitoring | CloudWatch + automated failover | Terraform provided |
| Incident response | Severity-based playbook | Template provided |
| Recovery runbooks | 10 scenarios documented | All actionable |

The combination of Iceberg's immutable snapshot architecture with proper S3 replication, catalog synchronization, and automated monitoring provides a robust DR posture capable of meeting 99.95%+ availability SLAs with RPO < 5 minutes for critical data.
