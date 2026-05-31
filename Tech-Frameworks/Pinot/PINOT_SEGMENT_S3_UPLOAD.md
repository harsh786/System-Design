# 🗄️ Pinot Segment Upload to S3 (Deep Store) — Complete Mechanics

## Why Deep Store Is Required

### The Core Problem Without Deep Store

```
┌─────────────────────────────────────────────────────────────────────┐
│ SCENARIO: Server crashes, no deep store configured                  │
│                                                                     │
│ Server-1 (holds segments A, B, C on local disk)                     │
│     ↓ CRASH (disk failure)                                          │
│                                                                     │
│ Result: Segments A, B, C are GONE FOREVER                           │
│         Data loss. Queries return incomplete results.                │
│         Recovery: Re-ingest from Kafka (hours/days of replay)       │
└─────────────────────────────────────────────────────────────────────┘
```

### What Deep Store Solves

```
┌─────────────────────────────────────────────────────────────────────┐
│ SCENARIO: Server crashes, deep store configured (S3)                │
│                                                                     │
│ Server-1 (holds segments A, B, C on local disk)                     │
│     ↓ CRASH (disk failure)                                          │
│                                                                     │
│ Deep Store (S3): segments A, B, C safely stored                     │
│     ↓                                                               │
│ Server-1 restarts → Downloads A, B, C from S3                       │
│ OR Server-2 takes over → Downloads A, B, C from S3                  │
│                                                                     │
│ Result: ZERO data loss. Recovery in minutes.                        │
└─────────────────────────────────────────────────────────────────────┘
```

### Deep Store = Single Source of Truth for Segments

| Concern | Without Deep Store | With Deep Store (S3) |
|---------|-------------------|---------------------|
| **Server crash** | Data loss | Download from S3 |
| **Disk failure** | Permanent loss | Download from S3 |
| **Server rebalance** | Copy from other servers (slow) | Download from S3 (fast, parallel) |
| **New server added** | Must replicate from peers | Download assigned segments from S3 |
| **Cluster migration** | Complex data movement | Point new cluster to same S3 bucket |
| **Disaster recovery** | Impossible | Restore from S3 in another region |
| **Cost** | Large local SSDs per server | Cheap S3 storage + smaller local SSDs |

---

## Deep Store Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         PINOT CLUSTER ARCHITECTURE                          │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐              │
│  │   Server 1   │     │   Server 2   │     │   Server 3   │              │
│  │ ┌──────────┐ │     │ ┌──────────┐ │     │ ┌──────────┐ │              │
│  │ │ Seg A    │ │     │ │ Seg D    │ │     │ │ Seg G    │ │              │
│  │ │ Seg B    │ │     │ │ Seg E    │ │     │ │ Seg H    │ │              │
│  │ │ Seg C    │ │     │ │ Seg F    │ │     │ │ Seg I    │ │              │
│  │ └──────────┘ │     │ └──────────┘ │     │ └──────────┘ │              │
│  │  Local Disk  │     │  Local Disk  │     │  Local Disk  │              │
│  └──────┬───────┘     └──────┬───────┘     └──────┬───────┘              │
│         │                    │                    │                        │
│         └────────────────────┼────────────────────┘                        │
│                              │                                             │
│                     Upload / Download                                       │
│                              │                                             │
│  ┌───────────────────────────▼───────────────────────────────────────┐    │
│  │                    DEEP STORE (S3 BUCKET)                          │    │
│  │                                                                    │    │
│  │  s3://pinot-segments/myTable/                                      │    │
│  │  ├── segA.tar.gz                                                   │    │
│  │  ├── segB.tar.gz                                                   │    │
│  │  ├── segC.tar.gz                                                   │    │
│  │  ├── segD.tar.gz                                                   │    │
│  │  ├── segE.tar.gz                                                   │    │
│  │  ├── ...                                                           │    │
│  │  └── segI.tar.gz                                                   │    │
│  │                                                                    │    │
│  │  Durability: 99.999999999% (11 nines)                              │    │
│  │  Cost: ~$0.023/GB/month (S3 Standard)                              │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                            │
│  ┌──────────────────┐                                                      │
│  │   Controller     │ ← Orchestrates uploads, tracks segment locations     │
│  │   (Helix)        │                                                      │
│  └──────────────────┘                                                      │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Supported Deep Store Backends

| Backend | URI Prefix | Best For | Config Class |
|---------|-----------|----------|--------------|
| **Amazon S3** | `s3://bucket/path` | AWS deployments | `S3PinotFS` |
| **Google Cloud Storage** | `gs://bucket/path` | GCP deployments | `GcsPinotFS` |
| **Azure Blob Storage** | `wasbs://container@account` | Azure deployments | `AzurePinotFS` |
| **HDFS** | `hdfs://namenode/path` | On-prem Hadoop clusters | `HadoopPinotFS` |
| **NFS** | `file:///mount/path` | Dev/test environments | `LocalPinotFS` |
| **ADLS Gen2** | `abfss://container@account` | Azure Data Lake | `AzurePinotFS` |

---

## Configuration: Enabling S3 Deep Store

### Controller Configuration

```properties
# controller.conf

# Deep store type
controller.data.dir=s3://my-pinot-bucket/pinot-data

# PinotFS class for S3
pinot.controller.storage.factory.class.s3=org.apache.pinot.plugin.filesystem.S3PinotFS

# S3 configuration
pinot.controller.storage.factory.s3.region=us-east-1
pinot.controller.storage.factory.s3.accessKey=AKIAIOSFODNN7EXAMPLE
pinot.controller.storage.factory.s3.secretKey=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY

# OR use IAM roles (recommended for production)
pinot.controller.storage.factory.s3.region=us-east-1
# No keys needed — uses instance role or IRSA (EKS)

# Segment upload timeout
pinot.controller.segment.upload.timeoutInMillis=600000
```

### Server Configuration

```properties
# server.conf

# Deep store access for download
pinot.server.storage.factory.class.s3=org.apache.pinot.plugin.filesystem.S3PinotFS
pinot.server.storage.factory.s3.region=us-east-1

# Local segment directory (cache)
pinot.server.instance.dataDir=/opt/pinot/data
pinot.server.instance.segmentTarDir=/opt/pinot/segment-tar
```

### Table Configuration (per table)

```json
{
  "tableName": "events_REALTIME",
  "tableType": "REALTIME",
  "segmentsConfig": {
    "replicasPerPartition": "2",
    "retentionTimeUnit": "DAYS",
    "retentionTimeValue": "30",
    "completionConfig": {
      "completionMode": "DOWNLOAD"
    }
  },
  "tenants": {
    "broker": "DefaultTenant",
    "server": "DefaultTenant"
  },
  "tableIndexConfig": {
    "streamConfigs": {
      "streamType": "kafka",
      "stream.kafka.topic.name": "events",
      "stream.kafka.broker.list": "kafka:9092",
      "stream.kafka.consumer.type": "lowlevel",
      "realtime.segment.flush.threshold.rows": "500000",
      "realtime.segment.flush.threshold.time": "1h"
    }
  },
  "metadata": {}
}
```

---

## How Segment Upload to S3 Works

### Flow 1: Offline Segment Upload (Batch Ingestion)

This is the simpler path — user pushes pre-built segments to controller.

```
┌─────────────────────────────────────────────────────────────────────┐
│              OFFLINE SEGMENT UPLOAD FLOW                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Step 1: Build segment externally (Spark/MapReduce/Pinot Admin)     │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │ Segment Builder (Spark Job / CLI)                         │       │
│  │                                                           │       │
│  │ Input: Raw data (Parquet, CSV, JSON, Avro)                │       │
│  │ Output: segment.tar.gz                                    │       │
│  │   ├── metadata.properties (segment name, time range, CRC) │       │
│  │   ├── creation.meta (schema version, builder info)        │       │
│  │   ├── columns/                                            │       │
│  │   │   ├── col1/                                           │       │
│  │   │   │   ├── forward_index (doc → value mapping)         │       │
│  │   │   │   ├── inverted_index (value → doc bitmap)         │       │
│  │   │   │   └── dictionary (distinct values)                │       │
│  │   │   ├── col2/                                           │       │
│  │   │   └── ...                                             │       │
│  │   └── star_tree/ (pre-aggregated data, if configured)     │       │
│  └──────────────────────────────────────────────────────────┘       │
│                                                                     │
│  Step 2: Upload to Controller via REST API                          │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │                                                           │       │
│  │ POST /v2/segments                                         │       │
│  │   Content-Type: multipart/form-data                       │       │
│  │   Body: segment.tar.gz                                    │       │
│  │                                                           │       │
│  │ OR                                                        │       │
│  │                                                           │       │
│  │ POST /v2/segments                                         │       │
│  │   Body: { "downloadUri": "s3://staging/segment.tar.gz" }  │       │
│  │   (Controller downloads from URI instead)                 │       │
│  │                                                           │       │
│  └──────────────────────────────────────────────────────────┘       │
│                                                                     │
│  Step 3: Controller processes upload                                │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │ Controller Actions:                                       │       │
│  │                                                           │       │
│  │ 1. Receive segment tar file                               │       │
│  │ 2. Extract and validate metadata:                         │       │
│  │    - Schema compatibility check                           │       │
│  │    - CRC validation                                       │       │
│  │    - Time range extraction                                │       │
│  │    - Segment name conflict check                          │       │
│  │ 3. Upload to Deep Store (S3):                             │       │
│  │    PUT s3://pinot-bucket/myTable_OFFLINE/segment.tar.gz   │       │
│  │ 4. Update ZooKeeper:                                      │       │
│  │    - Add segment to IdealState                            │       │
│  │    - Set download URI in segment ZNode                    │       │
│  │ 5. Helix assigns segment to servers                       │       │
│  │ 6. Servers download from S3 → local disk                  │       │
│  │ 7. Servers load segment into memory-mapped files          │       │
│  │ 8. Servers report ONLINE state to Helix                   │       │
│  └──────────────────────────────────────────────────────────┘       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**API Examples**:

```bash
# Method 1: Direct upload (segment file sent to controller)
curl -X POST \
  -F "file=@events_2026-01-15.tar.gz" \
  -H "Content-Type: multipart/form-data" \
  "http://pinot-controller:9000/v2/segments?tableName=events_OFFLINE"

# Method 2: URI-based upload (controller pulls from S3)
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "downloadUri": "s3://my-staging-bucket/segments/events_2026-01-15.tar.gz",
    "tableName": "events_OFFLINE"
  }' \
  "http://pinot-controller:9000/v2/segments"

# Method 3: Bulk ingestion (Spark-Pinot connector)
# In Spark job:
spark.read.parquet("s3://datalake/events/date=2026-01-15/")
  .write.format("pinot")
  .option("table", "events_OFFLINE")
  .option("pinotControllerUrl", "http://pinot-controller:9000")
  .save()
```

---

### Flow 2: Real-Time Segment Upload (After Sealing)

This is more complex — involves the segment completion protocol.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│              REAL-TIME SEGMENT COMPLETION + S3 UPLOAD FLOW                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Phase 1: CONSUMING (Active Ingestion)                                      │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │                                                                    │     │
│  │  Kafka Topic: "events" (partition 5)                               │     │
│  │       │                                                            │     │
│  │       ▼                                                            │     │
│  │  Server-2 (assigned partition 5):                                  │     │
│  │  ┌──────────────────────────────────────────────────┐              │     │
│  │  │ CONSUMING Segment: events__5__0__20260115T1000Z   │              │     │
│  │  │                                                   │              │     │
│  │  │ • In-memory MutableSegment (heap + off-heap)      │              │     │
│  │  │ • Forward index: RealtimeLuceneTextIndex           │              │     │
│  │  │ • Row count: 0 → 100K → 300K → 500K              │              │     │
│  │  │ • Kafka offset tracking: 1,000,000 → 1,500,000   │              │     │
│  │  │ • Current size: ~2.1 GB in memory                 │              │     │
│  │  └──────────────────────────────────────────────────┘              │     │
│  │                                                                    │     │
│  │  Seal Trigger (any one condition):                                 │     │
│  │  ✓ Row threshold:  rows >= 500,000                                 │     │
│  │  ✓ Time threshold: duration >= 1 hour                              │     │
│  │  ✓ Size threshold: memory >= 2 GB                                  │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                             │
│  Phase 2: SEALING (Conversion to Immutable)                                 │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │                                                                    │     │
│  │  Server-2 performs segment seal:                                    │     │
│  │                                                                    │     │
│  │  1. Stop consuming from Kafka (hold offset 1,500,000)              │     │
│  │  2. Convert MutableSegment → ImmutableSegment:                     │     │
│  │     a. Build sorted forward index (columnar format)                │     │
│  │     b. Build dictionary for each column                            │     │
│  │     c. Build inverted indexes (bitmap)                             │     │
│  │     d. Build range indexes (if configured)                         │     │
│  │     e. Build star-tree index (if configured)                       │     │
│  │     f. Compute CRC32 checksum                                      │     │
│  │     g. Write metadata.properties                                   │     │
│  │                                                                    │     │
│  │  3. Create segment tar file:                                       │     │
│  │     events__5__0__20260115T1000Z.tar.gz (~800 MB)                  │     │
│  │     (compressed from ~2.1 GB in-memory)                            │     │
│  │                                                                    │     │
│  │  Time taken: 30-120 seconds (depends on data size, indexes)        │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                             │
│  Phase 3: UPLOAD TO DEEP STORE (S3)                                         │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │                                                                    │     │
│  │  Server-2 uploads sealed segment to S3:                            │     │
│  │                                                                    │     │
│  │  PUT s3://pinot-segments/events_REALTIME/                          │     │
│  │      events__5__0__20260115T1000Z.tar.gz                           │     │
│  │                                                                    │     │
│  │  Upload mechanism:                                                 │     │
│  │  • File size < 5 GB: Single PUT (S3 PutObject)                     │     │
│  │  • File size >= 5 GB: Multipart upload                             │     │
│  │    - Part size: 64 MB (configurable)                               │     │
│  │    - Parallel upload threads: 4 (configurable)                     │     │
│  │    - Each part has its own ETag for verification                   │     │
│  │                                                                    │     │
│  │  Retry policy:                                                     │     │
│  │  • Max retries: 3                                                  │     │
│  │  • Backoff: exponential (1s, 2s, 4s)                               │     │
│  │  • On failure: segment stays in local tar dir for retry            │     │
│  │                                                                    │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                             │
│  Phase 4: COMMIT TO CONTROLLER                                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │                                                                    │     │
│  │  Server-2 → Controller: "Segment committed"                        │     │
│  │  {                                                                 │     │
│  │    "segmentName": "events__5__0__20260115T1000Z",                  │     │
│  │    "offset": 1500000,                                              │     │
│  │    "downloadUrl": "s3://pinot-segments/events_REALTIME/...",        │     │
│  │    "crc": "3a7b9c2d",                                             │     │
│  │    "buildTimeMs": 45000,                                           │     │
│  │    "sizeBytes": 838860800                                          │     │
│  │  }                                                                 │     │
│  │                                                                    │     │
│  │  Controller actions:                                               │     │
│  │  1. Validate CRC matches                                          │     │
│  │  2. Update IdealState: segment → ONLINE on Server-2                │     │
│  │  3. Create new CONSUMING segment:                                  │     │
│  │     events__5__1__20260115T1100Z (starts at offset 1,500,001)      │     │
│  │  4. If replicas > 1: Notify replica servers to download from S3    │     │
│  │                                                                    │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                             │
│  Phase 5: REPLICA DOWNLOAD (Segment Completion)                             │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │                                                                    │     │
│  │  completionConfig.completionMode = "DOWNLOAD" (recommended)        │     │
│  │                                                                    │     │
│  │  Server-3 (replica for partition 5):                               │     │
│  │  1. Was ALSO consuming from Kafka partition 5                      │     │
│  │  2. Receives signal: "Segment committed by Server-2"               │     │
│  │  3. DISCARDS its own in-memory consuming segment                   │     │
│  │  4. Downloads sealed segment from S3:                              │     │
│  │     GET s3://pinot-segments/events_REALTIME/                       │     │
│  │         events__5__0__20260115T1000Z.tar.gz                        │     │
│  │  5. Extracts to local disk                                         │     │
│  │  6. Loads as ONLINE segment                                        │     │
│  │  7. Reports ONLINE to Helix                                        │     │
│  │                                                                    │     │
│  │  Alternative: completionMode = "DEFAULT"                           │     │
│  │  → Replica builds its own segment independently                    │     │
│  │  → May produce slightly different segment (timing differences)     │     │
│  │  → NOT recommended for production                                  │     │
│  │                                                                    │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Segment Tar File Format

```
segment_name.tar.gz
├── metadata.properties
│     segment.name = events__5__0__20260115T1000Z
│     segment.total.docs = 500000
│     segment.crc = 3a7b9c2d
│     segment.start.time = 1736899200000
│     segment.end.time = 1736902800000
│     segment.index.version = v3
│     segment.creation.time = 1736903000000
│     segment.push.time = 1736903100000
│     segment.time.column = event_timestamp
│     segment.time.unit = MILLISECONDS
│
├── creation.meta
│     creator.name = RealtimeSegmentConverter
│     schema.version = 7
│     pinot.version = 0.12.0
│
├── v3/  (Segment format v3 — current default)
│   ├── columns/
│   │   ├── user_id/
│   │   │   ├── user_id.dict       (dictionary: distinct values)
│   │   │   ├── user_id.sv.fwd     (single-value forward index)
│   │   │   └── user_id.bitmap.inv (inverted index bitmap)
│   │   ├── event_type/
│   │   │   ├── event_type.dict
│   │   │   ├── event_type.sv.fwd
│   │   │   └── event_type.bitmap.inv
│   │   ├── event_timestamp/
│   │   │   ├── event_timestamp.sv.fwd (raw, no dictionary — high cardinality)
│   │   │   └── event_timestamp.range  (range index for time filters)
│   │   └── payload/
│   │       ├── payload.dict
│   │       └── payload.sv.fwd
│   │
│   ├── star_tree/
│   │   ├── star_tree_0/           (one per star-tree config)
│   │   │   ├── star_tree.bin      (tree structure)
│   │   │   └── star_tree_docs.bin (pre-aggregated records)
│   │   └── ...
│   │
│   └── index_map                   (offset map for mmap loading)
│
└── (end of tar)
```

---

## S3 Upload Mechanics (Internal Code Path)

### The Upload Pipeline

```java
// Simplified view of what happens internally

class RealtimeSegmentDataManager {
    
    void commitSegment(String segmentName, SegmentBuildInfo buildInfo) {
        // Step 1: Build immutable segment from mutable data
        File segmentDir = buildImmutableSegment(buildInfo);
        
        // Step 2: Create tar.gz
        File segmentTar = createSegmentTar(segmentDir, segmentName);
        
        // Step 3: Upload to deep store
        URI deepStoreUri = uploadToDeepStore(segmentTar, segmentName);
        
        // Step 4: Notify controller
        commitToController(segmentName, deepStoreUri, buildInfo.getOffset());
    }
    
    URI uploadToDeepStore(File segmentTar, String segmentName) {
        String deepStorePath = tableConfig.getDeepStorePrefix() 
            + "/" + segmentName + ".tar.gz";
        
        // PinotFS abstraction handles S3/GCS/HDFS/etc.
        pinotFS.copyFromLocalDir(segmentTar, new URI(deepStorePath));
        
        return new URI(deepStorePath);
    }
}
```

### S3-Specific Upload (Inside S3PinotFS)

```java
// Inside S3PinotFS.copyFromLocalDir()

void copyFromLocalDir(File localFile, URI s3Uri) {
    long fileSize = localFile.length();
    
    if (fileSize < MULTIPART_THRESHOLD) {  // Default: 5 GB
        // Simple single-part upload
        PutObjectRequest request = PutObjectRequest.builder()
            .bucket(getBucket(s3Uri))
            .key(getKey(s3Uri))
            .serverSideEncryption(ServerSideEncryption.AES256)
            .build();
        
        s3Client.putObject(request, localFile.toPath());
        
    } else {
        // Multipart upload for large segments
        multipartUpload(localFile, s3Uri);
    }
}

void multipartUpload(File localFile, URI s3Uri) {
    // 1. Initiate multipart upload
    CreateMultipartUploadResponse initResponse = s3Client.createMultipartUpload(
        CreateMultipartUploadRequest.builder()
            .bucket(bucket)
            .key(key)
            .build()
    );
    String uploadId = initResponse.uploadId();
    
    // 2. Upload parts in parallel (using thread pool)
    long partSize = 64 * 1024 * 1024;  // 64 MB parts
    List<CompletedPart> completedParts = new ArrayList<>();
    
    ExecutorService executor = Executors.newFixedThreadPool(4);
    List<Future<CompletedPart>> futures = new ArrayList<>();
    
    for (int partNum = 1; offset < fileSize; partNum++) {
        final int part = partNum;
        futures.add(executor.submit(() -> {
            UploadPartResponse response = s3Client.uploadPart(
                UploadPartRequest.builder()
                    .bucket(bucket)
                    .key(key)
                    .uploadId(uploadId)
                    .partNumber(part)
                    .build(),
                RequestBody.fromFile(localFile)  // with offset/length
            );
            return CompletedPart.builder()
                .partNumber(part)
                .eTag(response.eTag())
                .build();
        }));
    }
    
    // 3. Wait for all parts
    for (Future<CompletedPart> future : futures) {
        completedParts.add(future.get());
    }
    
    // 4. Complete multipart upload
    s3Client.completeMultipartUpload(
        CompleteMultipartUploadRequest.builder()
            .bucket(bucket)
            .key(key)
            .uploadId(uploadId)
            .multipartUpload(CompletedMultipartUpload.builder()
                .parts(completedParts)
                .build())
            .build()
    );
}
```

---

## Segment Download from S3

### When Does Download Happen?

| Trigger | Scenario | Urgency |
|---------|----------|---------|
| **Server restart** | Server boots up, assigned segments not on local disk | High |
| **Rebalance** | Segment moved from Server-A to Server-B | Medium |
| **Replica completion** | Peer committed segment, replica downloads | High |
| **Server replacement** | New server replaces failed server | High |
| **Scale-out** | New server added, takes over some segments | Medium |
| **Segment reload** | Admin triggers segment reload (schema change) | Low |

### Download Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     SEGMENT DOWNLOAD FLOW                                 │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. Server starts / receives segment assignment                          │
│     ├─ Check local disk: Is segment already present?                     │
│     │   ├─ YES + CRC matches → Skip download, load directly             │
│     │   ├─ YES + CRC mismatch → Delete local, re-download               │
│     │   └─ NO → Must download from deep store                            │
│     │                                                                    │
│  2. Download from S3                                                     │
│     ├─ Read segment ZNode from ZooKeeper to get download URI             │
│     ├─ GET s3://pinot-segments/table/segment.tar.gz                      │
│     ├─ Stream to local tar directory: /opt/pinot/segment-tar/            │
│     ├─ Verify CRC32 after download                                       │
│     │                                                                    │
│  3. Extract segment                                                      │
│     ├─ Untar to: /opt/pinot/data/tableName/segmentName/                  │
│     ├─ Validate all expected files present                               │
│     │                                                                    │
│  4. Load segment                                                         │
│     ├─ Memory-map (mmap) column files                                    │
│     ├─ Load dictionary into memory                                       │
│     ├─ Initialize inverted index readers                                 │
│     ├─ Load star-tree (if present)                                       │
│     │                                                                    │
│  5. Notify Helix                                                         │
│     └─ Transition: OFFLINE → ONLINE (segment is now queryable)           │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### Download Performance Optimization

```
Server startup with 500 segments to download:

NAIVE APPROACH (sequential):
┌────────────────────────────────────────────────────────────┐
│ Seg1 download → Seg2 download → ... → Seg500 download      │
│ Time: 500 × 10s = 5000s = 83 minutes 😱                    │
└────────────────────────────────────────────────────────────┘

PINOT'S APPROACH (parallel + prioritized):
┌────────────────────────────────────────────────────────────┐
│ Download thread pool: 8 parallel downloads                  │
│                                                            │
│ Thread 1: Seg1  → Seg9  → Seg17 → ...                      │
│ Thread 2: Seg2  → Seg10 → Seg18 → ...                      │
│ Thread 3: Seg3  → Seg11 → Seg19 → ...                      │
│ ...                                                        │
│ Thread 8: Seg8  → Seg16 → Seg24 → ...                      │
│                                                            │
│ Time: 500 / 8 × 10s = 625s = ~10 minutes ✓                 │
│                                                            │
│ Optimization: Segments with higher query traffic            │
│ are prioritized (from segment ZK metadata)                  │
└────────────────────────────────────────────────────────────┘
```

**Relevant server config**:
```properties
# Number of parallel segment download threads
pinot.server.instance.segment.store.uri=s3://pinot-segments
pinot.server.instance.max.parallel.segment.downloads=8

# Segment download timeout
pinot.server.instance.segment.download.timeout.ms=600000
```

---

## Failure Scenarios and Recovery

### Failure 1: Upload to S3 Fails During Seal

```
PROBLEM:
Server sealed segment successfully but S3 upload fails
(network issue, IAM permission expired, S3 throttling)

TIMELINE:
00:00  Segment sealed on Server-2 (local tar created)
00:01  Upload attempt #1 → FAIL (S3 503 SlowDown)
00:03  Upload attempt #2 → FAIL (S3 503 SlowDown)
00:07  Upload attempt #3 → FAIL (timeout)
00:07  Server marks segment as FAILED_UPLOAD

RECOVERY:
┌──────────────────────────────────────────────────────────┐
│ 1. Segment tar stays in local segmentTarDir              │
│ 2. Server periodically retries upload (background task)  │
│ 3. Controller monitors for segments stuck in CONSUMING   │
│ 4. If server crashes before upload succeeds:             │
│    → Kafka offset NOT committed                          │
│    → New consuming segment starts from SAME offset       │
│    → Data re-consumed, segment re-built, re-uploaded     │
│ 5. NO data loss (Kafka acts as source of truth)          │
└──────────────────────────────────────────────────────────┘

KEY INSIGHT: Kafka offset is committed ONLY after successful 
S3 upload + controller acknowledgment. This guarantees 
at-least-once delivery.
```

### Failure 2: Download from S3 Fails

```
PROBLEM:
Server assigned a segment but cannot download from S3
(network issue, S3 outage, corrupted file)

TIMELINE:
00:00  Server-3 assigned segment (rebalance)
00:01  Download attempt → FAIL (connection timeout)
00:05  Retry → FAIL (connection timeout)

RECOVERY:
┌──────────────────────────────────────────────────────────┐
│ State machine:                                           │
│                                                          │
│ OFFLINE → [downloading] → ERROR                          │
│                ↓                                         │
│         retry (exponential backoff: 10s, 20s, 40s, 80s)  │
│                ↓                                         │
│         max retries exceeded?                            │
│              ├── NO: retry again                         │
│              └── YES: alert, segment stays ERROR         │
│                                                          │
│ Impact:                                                  │
│ • If replication factor > 1: Other replica serves queries│
│ • If replication factor = 1: Segment unavailable         │
│ • Queries get partial results (missing this segment)     │
│                                                          │
│ Manual fix:                                              │
│ curl -X POST "http://controller:9000/segments/          │
│   myTable/segmentName/reload"                           │
│ → Forces re-download attempt                            │
└──────────────────────────────────────────────────────────┘
```

### Failure 3: S3 Region Outage

```
PROBLEM:
Entire S3 region is unavailable (rare but catastrophic)

IMPACT:
┌──────────────────────────────────────────────────────────┐
│ • Existing segments on servers: STILL QUERYABLE ✓        │
│   (segments are loaded from local disk, S3 is backup)    │
│                                                          │
│ • New segment seals: BLOCKED ✗                           │
│   (cannot upload to S3 → cannot commit offset)           │
│                                                          │
│ • Server restarts: CANNOT RECOVER ✗                      │
│   (cannot download segments that aren't on local disk)   │
│                                                          │
│ • Rebalance operations: BLOCKED ✗                        │
│   (cannot move segments between servers)                 │
└──────────────────────────────────────────────────────────┘

MITIGATION STRATEGIES:
1. S3 Cross-Region Replication (CRR):
   s3://pinot-segments-us-east-1 → s3://pinot-segments-us-west-2
   
2. Multi-region deep store configuration (Pinot 0.12+):
   controller.data.dir=s3://primary-bucket,s3://failover-bucket

3. Large local disk as buffer:
   • Keep 3 days of segments on local disk (not just latest)
   • Delays impact of S3 outage
   
4. Operational playbook:
   • If S3 down > 1 hour: Halt rebalances
   • If S3 down > 4 hours: Extend consuming segment thresholds
   • If S3 down > 24 hours: DR failover to secondary region
```

### Failure 4: CRC Mismatch After Download

```
PROBLEM:
Segment downloaded from S3 has different CRC than expected
(bit rot, incomplete upload, S3 object corruption)

DETECTION:
Server downloads segment → computes CRC → compares with ZK metadata

RECOVERY:
┌──────────────────────────────────────────────────────────┐
│ 1. Delete corrupted local file                           │
│ 2. Re-download from S3 (might be S3's issue, retry)      │
│ 3. If CRC still fails after 3 retries:                   │
│    a. Check if segment was recently replaced             │
│    b. If yes: fetch new URI from ZK                      │
│    c. If no: segment is corrupted in S3 itself           │
│       → Alert! Manual intervention required              │
│       → Rebuild segment from source (Kafka/batch)        │
│       → Upload replacement segment                       │
└──────────────────────────────────────────────────────────┘
```

---

## S3 Bucket Structure (Best Practices)

```
s3://pinot-deep-store/
├── pinot-data/
│   ├── events_REALTIME/
│   │   ├── events__0__0__20260115T0000Z.tar.gz
│   │   ├── events__0__1__20260115T0100Z.tar.gz
│   │   ├── events__0__2__20260115T0200Z.tar.gz
│   │   ├── events__1__0__20260115T0000Z.tar.gz
│   │   ├── events__1__1__20260115T0100Z.tar.gz
│   │   └── ... (partition__sequenceNumber__timestamp)
│   │
│   ├── events_OFFLINE/
│   │   ├── events_2026-01-14.tar.gz
│   │   ├── events_2026-01-15.tar.gz
│   │   └── events_2026-01-16.tar.gz
│   │
│   ├── user_profiles_OFFLINE/
│   │   ├── user_profiles_shard_0.tar.gz
│   │   ├── user_profiles_shard_1.tar.gz
│   │   └── user_profiles_shard_2.tar.gz
│   │
│   └── metrics_REALTIME/
│       ├── metrics__0__0__20260115T0000Z.tar.gz
│       └── ...
│
└── pinot-controller/
    └── ... (controller metadata, less critical)
```

### S3 Lifecycle Policies

```json
{
  "Rules": [
    {
      "ID": "TransitionToIA",
      "Status": "Enabled",
      "Filter": { "Prefix": "pinot-data/" },
      "Transitions": [
        {
          "Days": 30,
          "StorageClass": "STANDARD_IA"
        },
        {
          "Days": 90,
          "StorageClass": "GLACIER_INSTANT_RETRIEVAL"
        }
      ]
    },
    {
      "ID": "DeleteOldSegments",
      "Status": "Enabled",
      "Filter": { "Prefix": "pinot-data/events_REALTIME/" },
      "Expiration": { "Days": 365 }
    }
  ]
}
```

**Cost optimization**: Older segments rarely downloaded (only on server crash/rebalance). Glacier Instant Retrieval saves 68% on storage while maintaining millisecond access.

---

## IAM Permissions Required

### Minimum IAM Policy for Pinot (Controller + Servers)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PinotDeepStoreAccess",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket",
        "s3:GetBucketLocation",
        "s3:AbortMultipartUpload",
        "s3:ListMultipartUploadParts"
      ],
      "Resource": [
        "arn:aws:s3:::pinot-deep-store",
        "arn:aws:s3:::pinot-deep-store/*"
      ]
    }
  ]
}
```

### For EKS (IRSA — IAM Roles for Service Accounts)

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: pinot-server
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/PinotS3Role
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: pinot-controller
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/PinotS3Role
```

---

## Performance Tuning for S3 Operations

| Parameter | Default | Recommended | Impact |
|-----------|---------|-------------|--------|
| `s3.maxConnections` | 50 | 200 | More parallel uploads/downloads |
| `s3.multipartUploadPartSize` | 64 MB | 128 MB | Fewer parts for large segments |
| `s3.socketTimeout` | 50s | 120s | Avoids timeout on slow networks |
| `s3.connectionTimeout` | 10s | 30s | Tolerates slow DNS/handshake |
| `s3.maxRetries` | 3 | 5 | More resilient to transient errors |
| `server.max.parallel.segment.downloads` | 4 | 8 | Faster server startup |
| `server.segment.download.timeout.ms` | 300000 | 600000 | Allows large segment downloads |

### S3 Request Rate Optimization

```
PROBLEM: S3 has a per-prefix rate limit of 3,500 PUT/s and 5,500 GET/s

If all segments go to:
  s3://bucket/pinot-data/events_REALTIME/segment1.tar.gz
  s3://bucket/pinot-data/events_REALTIME/segment2.tar.gz
  ...
→ All requests hit SAME prefix → throttling!

SOLUTION: Partition by date or hash prefix:
  s3://bucket/pinot-data/events_REALTIME/2026/01/15/segment1.tar.gz
  s3://bucket/pinot-data/events_REALTIME/2026/01/15/segment2.tar.gz
  s3://bucket/pinot-data/events_REALTIME/2026/01/16/segment3.tar.gz

Note: S3 auto-partitions well now (since 2018), but date-based paths
still help with lifecycle policies and human navigation.
```

---

## Monitoring Deep Store Health

### Key Metrics to Track

```
# Upload metrics
pinot_server_segment_upload_duration_seconds{table, status}
pinot_server_segment_upload_size_bytes{table}
pinot_server_segment_upload_failures_total{table, error_type}

# Download metrics
pinot_server_segment_download_duration_seconds{table}
pinot_server_segment_download_size_bytes{table}
pinot_server_segment_download_failures_total{table, error_type}

# Deep store connectivity
pinot_deepstore_connection_errors_total{backend}
pinot_deepstore_latency_seconds{operation, backend}
```

### Alert Rules

```yaml
# Prometheus alert examples

- alert: PinotSegmentUploadFailing
  expr: rate(pinot_server_segment_upload_failures_total[5m]) > 0
  for: 10m
  labels:
    severity: critical
  annotations:
    summary: "Pinot segments failing to upload to S3"
    runbook: "Check S3 permissions, network, and disk space"

- alert: PinotSegmentDownloadSlow
  expr: pinot_server_segment_download_duration_seconds{quantile="0.99"} > 120
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Segment downloads from S3 are slow (>2min at p99)"
    
- alert: PinotServerStartupStalled
  expr: pinot_server_segments_loading > 0 AND rate(pinot_server_segments_loaded_total[10m]) == 0
  for: 15m
  labels:
    severity: critical
  annotations:
    summary: "Server has segments to load but no progress for 15 minutes"
```

---

## Key Takeaways

| Concept | Detail |
|---------|--------|
| **Why deep store?** | Segment durability, server recovery, rebalance, cost efficiency |
| **Who uploads?** | Server uploads after sealing real-time segments; Controller stores offline segments |
| **Upload format** | `.tar.gz` containing columnar indexes, dictionary, metadata |
| **Upload mechanism** | Single PUT for <5GB, multipart for larger segments |
| **When download happens** | Server restart, rebalance, replica completion, reload |
| **Failure safety** | Kafka offset committed only after S3 upload succeeds (at-least-once) |
| **Performance** | Parallel downloads (8 threads), local disk as cache, lazy loading |
| **Cost** | S3 Standard → IA (30d) → Glacier Instant (90d) lifecycle |
