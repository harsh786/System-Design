# Report Generation System

## 1. Requirements

### Functional Requirements
- **Template Management**: Create, version, and manage parameterized report templates using a Jinja-like DSL
- **Generation Modes**: Scheduled (cron-based) and on-demand report generation
- **Output Formats**: PDF, Excel (XLSX), CSV, HTML with format-specific optimizations
- **Large Dataset Handling**: Stream million-row reports without OOM via pipeline pattern
- **Caching/Memoization**: Parameter-hash deduplication, incremental refresh
- **Access Control**: Per-report RBAC with row-level security
- **Report Versioning**: Track template and output versions with diff capability
- **Drill-Through Links**: Clickable navigation between summary and detail reports
- **Embedded Visualizations**: Charts (bar, line, pie, heatmap) rendered inline

### Non-Functional Requirements
- **Availability**: 99.99% uptime for report API and delivery
- **Performance**: Generate 100-page PDF in <30 seconds
- **Concurrency**: Support 10,000 concurrent report generation jobs
- **Scalability**: Handle datasets up to 100M rows with streaming
- **Durability**: Generated reports retained per policy (30 days default)
- **Security**: Encrypt reports at rest and in transit, audit all access

## 2. Capacity Estimation

### Traffic
- Daily report generations: 500K (scheduled) + 200K (on-demand) = 700K/day
- Peak QPS: ~50 reports/second (burst to 200/s during business hours)
- Average report size: 5MB (PDF), 2MB (Excel), 500KB (CSV)

### Storage
- Daily artifact storage: 700K × 5MB avg = 3.5TB/day
- With 30-day retention: 105TB active storage
- Template storage: 50K templates × 50KB = 2.5GB (negligible)
- Cache storage: 20% hit rate × 700K × 5MB = 700GB hot cache

### Compute
- PDF rendering: 10s avg × 50 QPS = 500 concurrent workers needed
- Excel generation: 5s avg × 20 QPS = 100 workers
- CSV streaming: 2s avg × 30 QPS = 60 workers
- Total worker pool: ~700 workers at peak

### Network
- Egress: 700K × 5MB = 3.5TB/day outbound
- Internal: Worker → S3 writes at ~500MB/s sustained
- Data engine fetches: ~2TB/day from source databases

## 3. Data Modeling

### Database Schemas

```sql
-- Report Templates
CREATE TABLE report_templates (
    template_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                VARCHAR(255) NOT NULL,
    description         TEXT,
    version             INT NOT NULL DEFAULT 1,
    dsl_source          JSONB NOT NULL,          -- Template DSL AST
    compiled_template   BYTEA,                    -- Pre-compiled template bytecode
    parameters_schema   JSONB NOT NULL,           -- JSON Schema for params
    data_sources        JSONB NOT NULL,           -- Data source configurations
    output_formats      TEXT[] NOT NULL DEFAULT '{PDF,Excel,CSV,HTML}',
    owner_id            UUID NOT NULL REFERENCES users(user_id),
    org_id              UUID NOT NULL,
    access_policy       JSONB NOT NULL DEFAULT '{"visibility": "private"}',
    chart_configs       JSONB,                    -- Embedded chart definitions
    drill_through_links JSONB,                    -- Link definitions
    is_active           BOOLEAN DEFAULT true,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(org_id, name, version)
);

CREATE INDEX idx_templates_org ON report_templates(org_id, is_active);
CREATE INDEX idx_templates_owner ON report_templates(owner_id);
CREATE INDEX idx_templates_name ON report_templates(org_id, name);
CREATE INDEX idx_templates_gin ON report_templates USING GIN(dsl_source);

-- Report Generation Jobs
CREATE TABLE report_jobs (
    job_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id         UUID NOT NULL REFERENCES report_templates(template_id),
    template_version    INT NOT NULL,
    parameters          JSONB NOT NULL,           -- User-supplied params
    parameter_hash      VARCHAR(64) NOT NULL,     -- SHA-256 of canonical params
    output_format       VARCHAR(10) NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    priority            INT NOT NULL DEFAULT 5,   -- 1=highest, 10=lowest
    trigger_type        VARCHAR(20) NOT NULL,     -- SCHEDULED, ON_DEMAND, API
    requester_id        UUID NOT NULL,
    org_id              UUID NOT NULL,
    worker_id           VARCHAR(100),
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    error_message       TEXT,
    retry_count         INT DEFAULT 0,
    artifact_id         UUID REFERENCES report_artifacts(artifact_id),
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    CHECK (status IN ('PENDING','QUEUED','RUNNING','COMPLETED','FAILED','CANCELLED'))
);

CREATE INDEX idx_jobs_status ON report_jobs(status, priority, created_at);
CREATE INDEX idx_jobs_template ON report_jobs(template_id, status);
CREATE INDEX idx_jobs_requester ON report_jobs(requester_id, created_at DESC);
CREATE INDEX idx_jobs_param_hash ON report_jobs(template_id, parameter_hash, output_format);
CREATE INDEX idx_jobs_org_time ON report_jobs(org_id, created_at DESC);

-- Generated Artifacts
CREATE TABLE report_artifacts (
    artifact_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id              UUID NOT NULL REFERENCES report_jobs(job_id),
    template_id         UUID NOT NULL,
    storage_path        VARCHAR(512) NOT NULL,    -- S3 path
    storage_bucket      VARCHAR(100) NOT NULL,
    format              VARCHAR(10) NOT NULL,
    size_bytes          BIGINT NOT NULL,
    page_count          INT,
    row_count           BIGINT,
    checksum_sha256     VARCHAR(64) NOT NULL,
    encryption_key_id   VARCHAR(100),
    expires_at          TIMESTAMPTZ NOT NULL,
    download_count      INT DEFAULT 0,
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_artifacts_job ON report_artifacts(job_id);
CREATE INDEX idx_artifacts_template ON report_artifacts(template_id, created_at DESC);
CREATE INDEX idx_artifacts_expiry ON report_artifacts(expires_at) WHERE expires_at IS NOT NULL;

-- Cache Metadata
CREATE TABLE report_cache (
    cache_key           VARCHAR(128) PRIMARY KEY, -- template_id:param_hash:format
    artifact_id         UUID NOT NULL REFERENCES report_artifacts(artifact_id),
    template_id         UUID NOT NULL,
    parameter_hash      VARCHAR(64) NOT NULL,
    source_data_version VARCHAR(100),             -- Source watermark for invalidation
    ttl_seconds         INT NOT NULL,
    hit_count           INT DEFAULT 0,
    last_accessed_at    TIMESTAMPTZ DEFAULT NOW(),
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    expires_at          TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_cache_template ON report_cache(template_id);
CREATE INDEX idx_cache_expiry ON report_cache(expires_at);
CREATE INDEX idx_cache_access ON report_cache(last_accessed_at);

-- Report Schedules
CREATE TABLE report_schedules (
    schedule_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id         UUID NOT NULL REFERENCES report_templates(template_id),
    cron_expression     VARCHAR(100) NOT NULL,
    timezone            VARCHAR(50) DEFAULT 'UTC',
    parameters          JSONB NOT NULL,
    output_format       VARCHAR(10) NOT NULL,
    delivery_config     JSONB NOT NULL,           -- Email, S3, webhook destinations
    is_active           BOOLEAN DEFAULT true,
    next_run_at         TIMESTAMPTZ,
    last_run_at         TIMESTAMPTZ,
    last_run_status     VARCHAR(20),
    owner_id            UUID NOT NULL,
    org_id              UUID NOT NULL,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_schedules_next_run ON report_schedules(next_run_at) WHERE is_active = true;
CREATE INDEX idx_schedules_org ON report_schedules(org_id, is_active);

-- Access Control
CREATE TABLE report_permissions (
    permission_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id         UUID NOT NULL REFERENCES report_templates(template_id),
    principal_type      VARCHAR(10) NOT NULL,     -- USER, GROUP, ROLE
    principal_id        UUID NOT NULL,
    actions             TEXT[] NOT NULL,           -- VIEW, GENERATE, EDIT, DELETE, SHARE
    row_filter          JSONB,                    -- Row-level security expression
    column_mask         TEXT[],                   -- Columns to mask/hide
    granted_by          UUID NOT NULL,
    expires_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_permissions_template ON report_permissions(template_id);
CREATE INDEX idx_permissions_principal ON report_permissions(principal_type, principal_id);
```

### Kafka Topics Configuration

```yaml
topics:
  report-job-requests:
    partitions: 64
    replication-factor: 3
    retention.ms: 86400000        # 24 hours
    max.message.bytes: 1048576
    cleanup.policy: delete

  report-job-status:
    partitions: 32
    replication-factor: 3
    retention.ms: 604800000       # 7 days
    cleanup.policy: compact

  report-delivery-notifications:
    partitions: 16
    replication-factor: 3
    retention.ms: 259200000       # 3 days

  report-cache-invalidation:
    partitions: 8
    replication-factor: 3
    retention.ms: 3600000         # 1 hour
    cleanup.policy: delete
```

### Redis Configuration

```yaml
redis:
  job-queue:
    cluster: true
    nodes: 6
    maxmemory: 16gb
    maxmemory-policy: noeviction
    data-structures:
      - sorted-set: "jobs:priority:{org_id}"    # Priority queue
      - hash: "job:status:{job_id}"             # Job state
      - set: "workers:active"                    # Worker registry
      - string: "cache:lock:{cache_key}"        # Cache locks

  report-cache:
    cluster: true
    nodes: 6
    maxmemory: 64gb
    maxmemory-policy: allkeys-lfu
    data-structures:
      - string: "cache:meta:{cache_key}"        # Cache metadata
      - hash: "cache:stats:{template_id}"       # Hit/miss stats
```

## 4. High-Level Design

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              REPORT GENERATION SYSTEM                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐   │
│  │ Web UI / │───▶│  Report API  │───▶│  Job Queue   │───▶│   Worker Pool    │   │
│  │ SDK/CLI  │    │  (Gateway)   │    │  (Redis+Kafka)│    │  (Auto-scaling)  │   │
│  └──────────┘    └──────┬───────┘    └──────────────┘    └────────┬─────────┘   │
│                          │                                          │             │
│                          │                                          ▼             │
│                  ┌───────▼────────┐                    ┌────────────────────────┐ │
│                  │ Cache Layer    │                    │     Report Engine       │ │
│                  │ (Redis+S3)    │                    │  ┌──────────────────┐   │ │
│                  └───────────────┘                    │  │ Template Engine  │   │ │
│                                                       │  │ (DSL Parser+AST) │   │ │
│                                                       │  └────────┬─────────┘   │ │
│                                                       │           │              │ │
│                                                       │  ┌────────▼─────────┐   │ │
│                                                       │  │  Data Engine     │   │ │
│                                                       │  │ (Query+Stream)   │   │ │
│                                                       │  └────────┬─────────┘   │ │
│                                                       │           │              │ │
│                                                       │  ┌────────▼─────────┐   │ │
│                                                       │  │ Renderer         │   │ │
│                                                       │  │ (PDF/Excel/CSV)  │   │ │
│                                                       │  └────────┬─────────┘   │ │
│                                                       └───────────┼──────────────┘ │
│                                                                   │               │
│                          ┌────────────────────────────────────────┘               │
│                          ▼                                                         │
│  ┌──────────────────────────────────────────────────────────────────────────┐    │
│  │                         Storage Layer                                      │    │
│  │  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐   │    │
│  │  │ S3 Artifacts │  │  PostgreSQL  │  │  Chart Store  │  │   CDN       │   │    │
│  │  │ (Reports)    │  │  (Metadata)  │  │  (SVG/PNG)   │  │  (Delivery) │   │    │
│  │  └─────────────┘  └──────────────┘  └──────────────┘  └─────────────┘   │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
│                                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────────┐    │
│  │                       Delivery Layer                                       │    │
│  │  ┌──────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │    │
│  │  │  Email   │  │   Webhook    │  │  S3 Export   │  │  Slack/Teams     │  │    │
│  │  └──────────┘  └──────────────┘  └──────────────┘  └──────────────────┘  │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────┘

Data Flow:
  Request → API → Cache Check → [HIT] → Return cached artifact
                              → [MISS] → Enqueue Job → Worker picks up
                              → Template Parse → Data Fetch (streaming)
                              → Render (chunked) → Upload S3 → Notify
```

## 5. Low-Level Design (APIs)

### REST API Endpoints

```yaml
# Create Report Template
POST /api/v1/templates
Request:
  {
    "name": "Monthly Sales Report",
    "description": "Aggregated sales by region with trend charts",
    "dsl_source": {
      "type": "document",
      "sections": [
        {
          "type": "header",
          "content": "Sales Report - {{ params.month }} {{ params.year }}"
        },
        {
          "type": "data_section",
          "query": "SELECT region, SUM(revenue) FROM sales WHERE month = :month GROUP BY region",
          "data_source": "sales_db",
          "render_as": "table",
          "columns": ["Region", "Revenue"]
        },
        {
          "type": "chart",
          "chart_type": "bar",
          "data_ref": "section_1",
          "x_axis": "region",
          "y_axis": "revenue"
        },
        {
          "type": "loop",
          "over": "{{ data.regions }}",
          "as": "region",
          "body": {
            "type": "sub_report",
            "template_ref": "region_detail",
            "params": { "region": "{{ region.id }}" }
          }
        }
      ]
    },
    "parameters_schema": {
      "type": "object",
      "properties": {
        "month": { "type": "integer", "minimum": 1, "maximum": 12 },
        "year": { "type": "integer", "minimum": 2020 }
      },
      "required": ["month", "year"]
    },
    "data_sources": [
      { "name": "sales_db", "type": "postgresql", "connection_ref": "sales_prod" }
    ],
    "output_formats": ["PDF", "Excel", "CSV"]
  }
Response: 201
  {
    "template_id": "tmpl_a1b2c3d4",
    "version": 1,
    "status": "active",
    "created_at": "2024-01-15T10:30:00Z"
  }

# Generate Report (On-Demand)
POST /api/v1/reports/generate
Request:
  {
    "template_id": "tmpl_a1b2c3d4",
    "parameters": { "month": 12, "year": 2024 },
    "output_format": "PDF",
    "priority": "high",
    "delivery": {
      "type": "download",
      "notify": ["email:user@company.com"]
    }
  }
Response: 202
  {
    "job_id": "job_x7y8z9",
    "status": "QUEUED",
    "estimated_completion_seconds": 25,
    "poll_url": "/api/v1/reports/jobs/job_x7y8z9"
  }

# Get Job Status
GET /api/v1/reports/jobs/{job_id}
Response: 200
  {
    "job_id": "job_x7y8z9",
    "status": "RUNNING",
    "progress": {
      "phase": "rendering",
      "percent": 65,
      "pages_completed": 65,
      "total_pages_estimated": 100
    },
    "started_at": "2024-01-15T10:30:05Z",
    "estimated_remaining_seconds": 12
  }

# Get Completed Report
GET /api/v1/reports/jobs/{job_id}/artifact
Response: 200
  {
    "artifact_id": "art_m1n2o3",
    "download_url": "https://cdn.reports.example.com/art_m1n2o3?token=...",
    "format": "PDF",
    "size_bytes": 5242880,
    "page_count": 100,
    "generated_at": "2024-01-15T10:30:30Z",
    "expires_at": "2024-02-14T10:30:30Z",
    "checksum": "sha256:abc123..."
  }

# List Reports for User
GET /api/v1/reports?template_id=tmpl_a1b2c3d4&status=COMPLETED&limit=20&cursor=...
Response: 200
  {
    "reports": [...],
    "pagination": { "next_cursor": "...", "has_more": true }
  }

# Create Schedule
POST /api/v1/schedules
Request:
  {
    "template_id": "tmpl_a1b2c3d4",
    "cron": "0 8 1 * *",
    "timezone": "America/New_York",
    "parameters": { "month": "{{ now.month - 1 }}", "year": "{{ now.year }}" },
    "output_format": "PDF",
    "delivery": {
      "email": ["finance-team@company.com"],
      "s3": { "bucket": "reports-archive", "prefix": "monthly-sales/" }
    }
  }
Response: 201
  {
    "schedule_id": "sched_p4q5r6",
    "next_run_at": "2024-02-01T08:00:00-05:00"
  }
```

## 6. Deep Dive: Large Report Streaming

### Problem
Generating million-row reports with traditional approaches loads entire datasets into memory, causing OOM and slow generation. A 10M row report at 100 bytes/row = 1GB just for raw data.

### Solution: Pipeline-Based Streaming Generation

```python
import asyncio
from typing import AsyncGenerator
import hashlib

class StreamingReportGenerator:
    """
    Memory-bounded report generation using pipeline pattern.
    Data flows through: Source → Transform → Render → Output
    Each stage operates on chunks, never holding full dataset in memory.
    """
    
    MAX_MEMORY_BUDGET = 256 * 1024 * 1024  # 256MB per worker
    CHUNK_SIZE = 10000  # rows per chunk
    
    async def generate_streaming(self, job: ReportJob) -> str:
        """Main entry point for streaming generation."""
        template = await self.template_engine.load(job.template_id)
        data_plan = template.build_execution_plan(job.parameters)
        
        # Create bounded channels between pipeline stages
        data_channel = asyncio.Queue(maxsize=5)   # Back-pressure at 5 chunks
        render_channel = asyncio.Queue(maxsize=3)
        
        # S3 multipart upload for output
        upload = await self.s3.create_multipart_upload(
            bucket="report-artifacts",
            key=f"reports/{job.job_id}.{job.output_format.lower()}"
        )
        
        # Run pipeline stages concurrently
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self._fetch_stage(data_plan, data_channel))
            tg.create_task(self._render_stage(template, data_channel, render_channel, job))
            tg.create_task(self._output_stage(render_channel, upload, job))
        
        artifact_url = await upload.complete()
        return artifact_url
    
    async def _fetch_stage(self, plan: DataPlan, output: asyncio.Queue):
        """Cursor-based paginated data fetching from source databases."""
        for query_spec in plan.queries:
            cursor = None
            while True:
                # Fetch one chunk using server-side cursor
                chunk, cursor = await self.data_engine.fetch_chunk(
                    query=query_spec.sql,
                    params=query_spec.params,
                    cursor=cursor,
                    limit=self.CHUNK_SIZE
                )
                
                if not chunk.rows:
                    break
                    
                await output.put(DataChunk(
                    query_id=query_spec.id,
                    rows=chunk.rows,
                    columns=chunk.columns,
                    is_last=(cursor is None)
                ))
                
                if cursor is None:
                    break
        
        await output.put(None)  # Signal completion
    
    async def _render_stage(self, template, input_q: asyncio.Queue, 
                            output_q: asyncio.Queue, job: ReportJob):
        """Streaming template rendering - processes chunks as they arrive."""
        renderer = self._get_renderer(job.output_format)
        
        # Emit document header
        header = renderer.render_header(template, job.parameters)
        await output_q.put(OutputChunk(data=header, chunk_type="header"))
        
        # Process data chunks through template sections
        section_state = {}
        while True:
            chunk = await input_q.get()
            if chunk is None:
                break
            
            # Apply template transformations (formatting, calculated fields)
            transformed = template.transform_chunk(chunk, section_state)
            
            # Render chunk to output format
            rendered = renderer.render_data_chunk(transformed, template)
            await output_q.put(OutputChunk(data=rendered, chunk_type="body"))
            
            # Update progress
            section_state['rows_processed'] = section_state.get('rows_processed', 0) + len(chunk.rows)
            await self._update_progress(job, section_state['rows_processed'])
        
        # Render charts (parallel for performance)
        charts = await self._render_charts_parallel(template, section_state)
        for chart in charts:
            await output_q.put(OutputChunk(data=chart, chunk_type="chart"))
        
        # Emit footer
        footer = renderer.render_footer(template, section_state)
        await output_q.put(OutputChunk(data=footer, chunk_type="footer"))
        await output_q.put(None)
    
    async def _output_stage(self, input_q: asyncio.Queue, upload, job: ReportJob):
        """Chunked output to S3 using multipart upload."""
        part_number = 1
        buffer = bytearray()
        MIN_PART_SIZE = 5 * 1024 * 1024  # S3 minimum part size
        
        while True:
            chunk = await input_q.get()
            if chunk is None:
                break
            
            buffer.extend(chunk.data)
            
            # Upload when buffer exceeds minimum part size
            if len(buffer) >= MIN_PART_SIZE:
                await upload.upload_part(
                    part_number=part_number,
                    body=bytes(buffer)
                )
                part_number += 1
                buffer.clear()
        
        # Upload remaining buffer
        if buffer:
            await upload.upload_part(part_number=part_number, body=bytes(buffer))
    
    async def _render_charts_parallel(self, template, state: dict) -> list:
        """Render all charts in parallel using Puppeteer cluster."""
        chart_configs = template.get_chart_configs()
        
        async def render_single_chart(config):
            chart_data = state.get(f"aggregation:{config.data_ref}")
            svg = await self.chart_service.render(
                chart_type=config.chart_type,
                data=chart_data,
                options=config.options
            )
            return svg
        
        tasks = [render_single_chart(c) for c in chart_configs]
        return await asyncio.gather(*tasks)
```

### Memory Management

```
┌─────────────────────────────────────────────────────────┐
│              Memory Budget: 256MB per Worker              │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  Fetch Buffer:   50MB  (5 chunks × 10K rows × ~1KB)     │
│  Render Buffer:  100MB (template state + partial output) │
│  Output Buffer:  50MB  (S3 upload accumulator)           │
│  Charts:         50MB  (parallel chart rendering)        │
│  Overhead:       6MB   (runtime, GC headroom)            │
│                                                           │
│  Back-pressure: Queue full → fetch pauses                │
│  Result: Constant memory regardless of report size       │
└─────────────────────────────────────────────────────────┘
```

## 7. Deep Dive: Template Engine Internals

### DSL Parsing and AST

```python
from dataclasses import dataclass
from typing import List, Optional, Any
import re

@dataclass
class ASTNode:
    node_type: str
    children: List['ASTNode']
    attributes: dict

class TemplateDSLParser:
    """
    Parses report template DSL into executable AST.
    Supports: variables, conditionals, loops, sub-reports, charts.
    """
    
    EXPRESSION_PATTERN = re.compile(r'\{\{\s*(.+?)\s*\}\}')
    
    def parse(self, dsl_source: dict) -> ASTNode:
        """Parse DSL JSON into AST."""
        return self._parse_node(dsl_source)
    
    def _parse_node(self, node: dict) -> ASTNode:
        node_type = node['type']
        
        if node_type == 'document':
            children = [self._parse_node(s) for s in node['sections']]
            return ASTNode('document', children, {})
        
        elif node_type == 'header':
            expr = self._parse_expression(node['content'])
            return ASTNode('header', [], {'expression': expr})
        
        elif node_type == 'data_section':
            return ASTNode('data_section', [], {
                'query': self._parse_query(node['query']),
                'data_source': node['data_source'],
                'render_as': node.get('render_as', 'table'),
                'columns': node.get('columns'),
                'sort': node.get('sort'),
                'filters': node.get('filters', [])
            })
        
        elif node_type == 'conditional':
            condition = self._parse_expression(node['condition'])
            then_branch = [self._parse_node(n) for n in node['then']]
            else_branch = [self._parse_node(n) for n in node.get('else', [])]
            return ASTNode('conditional', then_branch + else_branch, {
                'condition': condition,
                'then_count': len(then_branch)
            })
        
        elif node_type == 'loop':
            body = self._parse_node(node['body'])
            return ASTNode('loop', [body], {
                'iterable': self._parse_expression(node['over']),
                'variable': node['as'],
                'batch_size': node.get('batch_size', 1000)
            })
        
        elif node_type == 'chart':
            return ASTNode('chart', [], {
                'chart_type': node['chart_type'],
                'data_ref': node['data_ref'],
                'x_axis': node['x_axis'],
                'y_axis': node['y_axis'],
                'options': node.get('options', {})
            })
        
        elif node_type == 'sub_report':
            params = {k: self._parse_expression(v) for k, v in node['params'].items()}
            return ASTNode('sub_report', [], {
                'template_ref': node['template_ref'],
                'params': params
            })
        
        raise ValueError(f"Unknown node type: {node_type}")
    
    def _parse_expression(self, expr_str: str) -> 'Expression':
        """Parse {{ expression }} into evaluable Expression object."""
        parts = []
        last_end = 0
        
        for match in self.EXPRESSION_PATTERN.finditer(expr_str):
            if match.start() > last_end:
                parts.append(LiteralExpr(expr_str[last_end:match.start()]))
            parts.append(DynamicExpr(match.group(1)))
            last_end = match.end()
        
        if last_end < len(expr_str):
            parts.append(LiteralExpr(expr_str[last_end:]))
        
        return CompositeExpr(parts) if len(parts) > 1 else parts[0]


class LazyDataBinder:
    """
    Binds data to template with lazy evaluation.
    Data is only fetched when a section actually needs it.
    """
    
    def __init__(self, data_engine, parameters: dict):
        self.data_engine = data_engine
        self.parameters = parameters
        self._cache = {}  # Memoize evaluated data refs
    
    async def resolve(self, expression: 'Expression', context: dict) -> Any:
        """Lazily resolve expression - fetches data only when needed."""
        if isinstance(expression, DynamicExpr):
            path = expression.path
            
            # Check if it's a data reference
            if path.startswith('data.'):
                data_ref = path[5:]
                if data_ref not in self._cache:
                    self._cache[data_ref] = await self._fetch_data(data_ref)
                return self._navigate(self._cache[data_ref], path[5+len(data_ref.split('.')[0]):])
            
            # Parameter reference
            if path.startswith('params.'):
                return self._navigate(self.parameters, path[7:])
            
            # Context variable (loop variable, etc.)
            return self._navigate(context, path)
        
        return expression.evaluate(context)
    
    async def _fetch_data(self, ref: str):
        """Fetch data for a reference - with batched query optimization."""
        # Batch multiple pending data fetches into single query when possible
        return await self.data_engine.execute_ref(ref, self.parameters)


class QueryOptimizer:
    """Optimizes queries within loops to use batched execution."""
    
    def optimize_loop_queries(self, loop_node: ASTNode, parent_data) -> List[dict]:
        """
        Instead of N queries for N loop iterations,
        batch into single query with IN clause.
        """
        if loop_node.attributes.get('batch_size'):
            # Collect all iteration keys
            iterable = loop_node.attributes['iterable']
            items = list(parent_data)
            
            # Batch queries: instead of SELECT ... WHERE id = ? (N times)
            # Use: SELECT ... WHERE id IN (batch) (N/batch_size times)
            batch_size = loop_node.attributes['batch_size']
            batches = [items[i:i+batch_size] for i in range(0, len(items), batch_size)]
            
            return batches
        
        return [[item] for item in parent_data]
```

## 8. Deep Dive: Caching Strategy

### Parameter-Hash Based Deduplication

```python
import hashlib
import json
from datetime import datetime, timedelta

class ReportCacheManager:
    """
    Intelligent caching with parameter-hash dedup,
    incremental refresh, and pre-warming.
    """
    
    def __init__(self, redis_client, s3_client, db):
        self.redis = redis_client
        self.s3 = s3_client
        self.db = db
    
    def compute_cache_key(self, template_id: str, parameters: dict, 
                          output_format: str) -> str:
        """
        Compute deterministic cache key from canonical parameters.
        Handles parameter normalization (sorting, type coercion).
        """
        # Canonicalize parameters (sort keys, normalize values)
        canonical = json.dumps(parameters, sort_keys=True, default=str)
        param_hash = hashlib.sha256(canonical.encode()).hexdigest()[:16]
        return f"{template_id}:{param_hash}:{output_format.lower()}"
    
    async def get_cached(self, cache_key: str) -> Optional[CacheResult]:
        """Check cache with freshness validation."""
        meta = await self.redis.hgetall(f"cache:meta:{cache_key}")
        if not meta:
            return None
        
        # Check if source data has changed (incremental refresh)
        if await self._is_stale(meta):
            await self.redis.delete(f"cache:meta:{cache_key}")
            return None
        
        # Update access stats
        await self.redis.hincrby(f"cache:meta:{cache_key}", "hit_count", 1)
        await self.redis.hset(f"cache:meta:{cache_key}", "last_accessed", 
                             datetime.utcnow().isoformat())
        
        return CacheResult(
            artifact_id=meta['artifact_id'],
            download_url=await self.s3.generate_presigned_url(meta['storage_path']),
            cached_at=meta['created_at']
        )
    
    async def _is_stale(self, meta: dict) -> bool:
        """
        Detect source data changes for time-range reports.
        Uses watermark comparison against source tables.
        """
        source_version = meta.get('source_data_version')
        if not source_version:
            return False  # No version tracking, rely on TTL only
        
        template_id = meta['template_id']
        template = await self.db.get_template(template_id)
        
        for ds in template.data_sources:
            current_watermark = await self.data_engine.get_watermark(
                data_source=ds['name'],
                table=ds.get('change_tracking_table')
            )
            if current_watermark != source_version:
                return True
        
        return False
    
    async def put_cached(self, cache_key: str, artifact_id: str, 
                         template_id: str, parameters: dict,
                         source_version: str = None):
        """Store cache entry with appropriate TTL."""
        ttl = self._compute_ttl(template_id, parameters)
        
        await self.redis.hset(f"cache:meta:{cache_key}", mapping={
            'artifact_id': artifact_id,
            'template_id': template_id,
            'source_data_version': source_version or '',
            'created_at': datetime.utcnow().isoformat(),
            'hit_count': 0,
            'last_accessed': datetime.utcnow().isoformat()
        })
        await self.redis.expire(f"cache:meta:{cache_key}", ttl)
    
    def _compute_ttl(self, template_id: str, parameters: dict) -> int:
        """
        TTL strategy by report type:
        - Historical reports (past dates): 24 hours (data won't change)
        - Current period reports: 1 hour (data updating)
        - Real-time reports: 5 minutes
        """
        # Check if parameters contain only historical dates
        if self._is_historical(parameters):
            return 86400  # 24 hours
        elif self._is_current_period(parameters):
            return 3600   # 1 hour
        else:
            return 300    # 5 minutes
    
    async def pre_warm_scheduled(self):
        """
        Pre-warm cache for scheduled reports.
        Run 10 minutes before scheduled execution time.
        """
        upcoming = await self.db.get_schedules_due_within(minutes=15)
        
        for schedule in upcoming:
            cache_key = self.compute_cache_key(
                schedule.template_id,
                schedule.resolved_parameters(),
                schedule.output_format
            )
            
            # Only pre-warm if not already cached
            if not await self.redis.exists(f"cache:meta:{cache_key}"):
                await self.enqueue_prewarm_job(schedule)


class IncrementalRefreshDetector:
    """Detects whether a cached report needs refresh based on source changes."""
    
    async def get_watermark(self, data_source: str, table: str) -> str:
        """
        Get current data watermark using:
        1. Change tracking (SQL Server) / logical replication slot (PG)
        2. MAX(updated_at) as fallback
        3. Row count hash for tables without timestamps
        """
        if self.supports_change_tracking(data_source):
            return await self._get_ct_version(data_source, table)
        
        # Fallback: hash of max timestamp + count
        result = await self.execute(data_source, 
            f"SELECT MAX(updated_at), COUNT(*) FROM {table}")
        return hashlib.md5(str(result).encode()).hexdigest()
```

### Cache Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Cache Flow                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Request(template_id, params, format)                            │
│       │                                                           │
│       ▼                                                           │
│  ┌─────────────────┐                                             │
│  │ Compute Cache Key│  key = sha256(canonical(params))           │
│  │ template:hash:fmt│                                             │
│  └────────┬────────┘                                             │
│           ▼                                                       │
│  ┌─────────────────┐  HIT   ┌─────────────────────┐            │
│  │  Redis Lookup   │───────▶│  Staleness Check     │            │
│  └────────┬────────┘        └──────────┬──────────┘            │
│           │ MISS                        │                        │
│           ▼                     FRESH   │   STALE                │
│  ┌─────────────────┐            ▼       ▼                        │
│  │  Generate Report│     Return S3 URL  Invalidate + Regenerate  │
│  └────────┬────────┘                                             │
│           │                                                       │
│           ▼                                                       │
│  ┌─────────────────┐                                             │
│  │ Store in Cache  │  TTL based on report type                   │
│  │ + Upload to S3  │                                             │
│  └─────────────────┘                                             │
└─────────────────────────────────────────────────────────────────┘
```

## 9. Component Optimization

### Puppeteer Cluster for PDF Rendering

```python
class PuppeteerPDFCluster:
    """
    Pool of Puppeteer browser instances for PDF rendering.
    Pre-warmed browsers avoid cold-start latency.
    """
    
    def __init__(self, pool_size: int = 20):
        self.pool_size = pool_size
        self.browsers = asyncio.Queue(maxsize=pool_size)
    
    async def initialize(self):
        """Pre-warm browser pool."""
        for _ in range(self.pool_size):
            browser = await pyppeteer.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-gpu',
                    '--disable-dev-shm-usage',
                    '--font-render-hinting=none',  # Consistent rendering
                ]
            )
            await self.browsers.put(browser)
    
    async def render_pdf(self, html_content: str, options: dict) -> bytes:
        """Render HTML to PDF using pooled browser."""
        browser = await self.browsers.get()
        try:
            page = await browser.newPage()
            await page.setContent(html_content, waitUntil='networkidle0')
            
            pdf_bytes = await page.pdf({
                'format': options.get('page_size', 'A4'),
                'printBackground': True,
                'margin': {'top': '1cm', 'bottom': '1cm', 'left': '1cm', 'right': '1cm'},
                'displayHeaderFooter': True,
                'headerTemplate': options.get('header_html', ''),
                'footerTemplate': options.get('footer_html', '<span class="pageNumber"></span>'),
            })
            
            await page.close()
            return pdf_bytes
        finally:
            await self.browsers.put(browser)
```

### Worker Pool Auto-Scaling

```yaml
# Kubernetes HPA for report workers
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: report-worker-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: report-workers
  minReplicas: 50
  maxReplicas: 1000
  metrics:
    - type: External
      external:
        metric:
          name: redis_queue_depth
          selector:
            matchLabels:
              queue: report-jobs
        target:
          type: AverageValue
          averageValue: "5"  # Scale up when >5 jobs per worker
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 70
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 30
      policies:
        - type: Percent
          value: 100
          periodSeconds: 30
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Percent
          value: 10
          periodSeconds: 60
```

## 10. Observability

### Metrics

```yaml
metrics:
  - report.jobs.submitted:         Counter (tags: template_id, format, trigger_type)
  - report.jobs.completed:         Counter (tags: template_id, format, status)
  - report.jobs.duration_ms:       Histogram (tags: template_id, format)
  - report.jobs.queue_wait_ms:     Histogram (tags: priority)
  - report.cache.hit_rate:         Gauge (tags: template_id)
  - report.cache.stale_detected:   Counter (tags: template_id)
  - report.rendering.pages_per_sec: Gauge (tags: format)
  - report.data.rows_fetched:      Counter (tags: data_source)
  - report.data.fetch_duration_ms: Histogram (tags: data_source)
  - report.output.size_bytes:      Histogram (tags: format)
  - report.workers.active:         Gauge
  - report.workers.memory_usage:   Gauge (tags: worker_id)
  - report.delivery.success:       Counter (tags: channel)
  - report.delivery.failure:       Counter (tags: channel, error_type)

alerts:
  - name: HighJobQueueDepth
    condition: redis_queue_depth > 1000 for 5m
    severity: warning
  - name: SlowPDFGeneration
    condition: p95(report.jobs.duration_ms{format=PDF}) > 60000
    severity: critical
  - name: WorkerOOM
    condition: report.workers.memory_usage > 240MB
    severity: critical
  - name: CacheHitRateLow
    condition: report.cache.hit_rate < 0.15 for 30m
    severity: warning
```

### Distributed Tracing

```
Trace: GenerateReport(job_id=job_x7y8z9)
├── [2ms]   API: ValidateRequest
├── [1ms]   Cache: CheckHit (MISS)
├── [3ms]   Queue: EnqueueJob
├── [150ms] Worker: PickupJob
├── [5ms]   Template: LoadAndParse
├── [8000ms] Data: FetchStreaming
│   ├── [3000ms] Query: sales_summary (150K rows)
│   ├── [4000ms] Query: region_details (800K rows)
│   └── [1000ms] Query: trend_data (50K rows)
├── [15000ms] Render: StreamingGeneration
│   ├── [2000ms] Render: Header+TOC
│   ├── [8000ms] Render: DataSections (100 pages)
│   ├── [3000ms] Render: Charts (8 parallel)
│   └── [2000ms] Render: Footer+Summary
├── [3000ms] Output: S3MultipartUpload (5.2MB, 2 parts)
├── [50ms]  Cache: Store
└── [200ms] Delivery: Notify (email + webhook)
Total: 26.4s ✓ (< 30s SLA)
```

## 11. Considerations

### Trade-offs
| Decision | Chosen | Alternative | Rationale |
|----------|--------|-------------|-----------|
| Job Queue | Redis + Kafka | RabbitMQ | Redis for priority queue speed; Kafka for durability/replay |
| PDF Engine | Puppeteer cluster | wkhtmltopdf | Better CSS/JS support, chart rendering fidelity |
| Storage | S3 + CDN | Local disk | Scalability, durability, CDN for fast delivery |
| Streaming | Pipeline pattern | Map-reduce | Lower latency, memory-bounded, simpler for report use case |
| Cache Key | Parameter hash | Full param storage | Space efficient, collision-resistant with SHA-256 |

### Failure Handling
- **Worker crash mid-generation**: Job timeout → re-enqueue with retry count
- **S3 upload failure**: Multipart upload abort + retry from last successful part
- **Source DB unavailable**: Circuit breaker with exponential backoff, serve stale cache
- **OOM prevention**: Memory watchdog kills job if >256MB, re-routes to high-memory worker pool

### Security
- Reports encrypted at rest (AES-256-GCM) with per-org keys
- Presigned URLs with 1-hour expiry for download
- Row-level security enforced at data fetch time
- Template injection prevention: sandboxed expression evaluation, no arbitrary code execution

### Future Enhancements
- Interactive reports (HTML with client-side drill-through)
- Collaborative report building (real-time template editor)
- ML-powered auto-insights (anomaly detection in report data)
- Natural language report requests ("Show me Q4 sales by region")
