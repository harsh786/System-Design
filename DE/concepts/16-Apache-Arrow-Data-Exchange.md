# Apache Arrow & Data Exchange - Staff/Architect Deep Dive

## 1. Arrow Fundamentals

### The Problem Arrow Solves

```
┌─────────────────────────────────────────────────────────────────┐
│                    BEFORE ARROW                                   │
│                                                                   │
│  Spark ──serialize──> bytes ──deserialize──> Pandas              │
│  Pandas ──serialize──> bytes ──deserialize──> R                  │
│  R ──serialize──> bytes ──deserialize──> DuckDB                  │
│                                                                   │
│  N systems = N×(N-1) conversion paths                            │
│  Each conversion: CPU + memory + latency                         │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    WITH ARROW                                     │
│                                                                   │
│  Spark ──┐                                                       │
│  Pandas ─┼──> Arrow Format (universal) ──┼──> Any consumer       │
│  R ──────┘                               └──> Zero-copy!         │
│                                                                   │
│  N systems = 1 common format                                     │
│  Zero serialization overhead between compatible systems          │
└─────────────────────────────────────────────────────────────────┘
```

**Core value proposition**: A universal, language-agnostic, in-memory columnar data format that eliminates serialization/deserialization between analytical engines.

### Arrow vs Parquet - Critical Distinction

| Aspect | Arrow | Parquet |
|--------|-------|---------|
| Purpose | In-memory processing | On-disk storage |
| Layout | Columnar, uncompressed | Columnar, compressed |
| Random access | O(1) | Requires decompression |
| Mutability | Immutable batches | Immutable files |
| Encoding | Dictionary, run-end | Dictionary, RLE, delta, hybrid |
| Compression | Optional (LZ4/ZSTD) | Always (Snappy/ZSTD/Gzip) |
| Zero-copy | Yes | No (must decompress) |
| Use case | Interchange, compute | Archival, data lake |

**Key insight**: Parquet is Arrow's on-disk complement. Arrow reads Parquet efficiently because both are columnar - the read path is column-chunk → decompress → decode → Arrow buffer.

### Columnar Memory Layout

#### Fixed-Width Types (Int32, Float64, Date32)

```
Buffer Layout for Int32 column [1, null, 3, 4, null]:

Validity Bitmap Buffer (1 byte, padded to 64 bytes):
┌─────────────────────────────────────────────────────────────────┐
│ Bit 0=1, Bit 1=0, Bit 2=1, Bit 3=1, Bit 4=0                   │
│ Binary: 00011011 = 0x1B                                          │
│ (LSB first: bit[i] = 1 means value[i] is valid)                 │
└─────────────────────────────────────────────────────────────────┘

Values Buffer (5 × 4 bytes = 20 bytes, padded to 64 bytes):
┌──────┬──────┬──────┬──────┬──────┐
│  1   │  ??  │  3   │  4   │  ??  │   (null slots have undefined values)
│4bytes│4bytes│4bytes│4bytes│4bytes│
└──────┴──────┴──────┴──────┴──────┘
```

#### Variable-Width Types (Utf8/String, Binary)

```
Column: ["hello", null, "world", "!"]

Validity Bitmap: 1101 = 0x0B

Offsets Buffer (int32, length = n+1 = 5 entries):
┌───┬───┬───┬────┬────┐
│ 0 │ 5 │ 5 │ 10 │ 11 │
└───┴───┴───┴────┴────┘
  ↓       ↓        ↓
  start   null     end
          (offset unchanged)

Data Buffer:
┌─────────────────────────┐
│ h e l l o w o r l d !   │
└─────────────────────────┘
  0         5         10 11

String[i] = data[offsets[i] : offsets[i+1]]
String[0] = data[0:5]  = "hello"
String[2] = data[5:10] = "world"
String[3] = data[10:11] = "!"
```

#### Large Variable-Width (LargeUtf8, LargeBinary)

Same as above but offsets are int64 - supports >2GB data buffers.

#### Nested Types - List

```
Column: [[1, 2], null, [3, 4, 5]]

Validity Bitmap: 101 = 0x05

Offsets Buffer (int32):
┌───┬───┬───┬───┐
│ 0 │ 2 │ 2 │ 5 │
└───┴───┴───┴───┘

Child Array (Int32, flat):
Values: [1, 2, 3, 4, 5]
Validity: 11111

List[i] = child[offsets[i] : offsets[i+1]]
List[0] = child[0:2] = [1, 2]
List[2] = child[2:5] = [3, 4, 5]
```

#### Nested Types - Struct

```
Column: Struct<name: Utf8, age: Int32>
[{"Alice", 30}, null, {"Bob", 25}]

Validity Bitmap: 101 (struct-level nulls)

Child 0 (name: Utf8): ["Alice", ??, "Bob"]  (child validity follows parent)
Child 1 (age: Int32): [30, ??, 25]
```

### Validity Bitmaps

- **Bit order**: LSB (Least Significant Bit) numbering
- **Bit value**: 1 = valid, 0 = null
- **Padding**: Always padded to 64-byte boundaries
- **Absence**: If null_count = 0, validity bitmap buffer may be absent (all valid)

```python
# Checking validity in bitmap
def is_valid(bitmap_bytes, index):
    byte_index = index // 8
    bit_index = index % 8
    return (bitmap_bytes[byte_index] >> bit_index) & 1 == 1
```

### 64-Byte Aligned Buffers

All buffers are aligned to 64-byte boundaries for:
- **SIMD**: AVX-512 operates on 512-bit (64-byte) vectors
- **Cache lines**: Most CPUs have 64-byte cache lines
- **Memory mapping**: OS page alignment compatibility
- **GPU**: CUDA memory alignment requirements

```
Buffer allocation:
┌────────────────────────────────────────────────────────────────────┐
│ 64-byte aligned start                                              │
│ ├── Validity bitmap (padded to 64B)                                │
│ ├── Offsets buffer (padded to 64B)                                 │
│ └── Data buffer (padded to 64B)                                    │
└────────────────────────────────────────────────────────────────────┘
```

### Record Batches

A RecordBatch = Schema + ordered collection of equal-length Arrays.

```
RecordBatch (num_rows = 1024):
┌─────────────────────────────────────────────┐
│ Schema: {id: Int64, name: Utf8, amt: Float64}│
├─────────────────────────────────────────────┤
│ Column 0 (id):   [buffers...]               │
│ Column 1 (name): [buffers...]               │
│ Column 2 (amt):  [buffers...]               │
└─────────────────────────────────────────────┘
```

**Why batches?**
- Amortize metadata overhead
- Enable vectorized processing
- Natural unit for streaming (one batch per message)
- Typical sizes: 64K-1M rows for compute, smaller for streaming

### Dictionary Encoding

```
Column: ["red", "blue", "red", "red", "green", "blue"]

Without dictionary: 6 strings in Utf8 array
With dictionary:
  Dictionary (Utf8): ["red", "blue", "green"]  (indices 0, 1, 2)
  Indices (Int8):    [0, 1, 0, 0, 2, 1]

Memory savings: especially for low-cardinality columns
Performance: comparisons on indices (int) vs strings
```

```python
import pyarrow as pa

# Create dictionary-encoded array
arr = pa.array(["red", "blue", "red", "red", "green", "blue"])
dict_arr = arr.dictionary_encode()

print(dict_arr.type)          # dictionary<values=string, indices=int32>
print(dict_arr.dictionary)    # ["red", "blue", "green"]
print(dict_arr.indices)       # [0, 1, 0, 0, 2, 1]
```

### Zero-Copy Slicing

```python
import pyarrow as pa

# Original array: 1M integers
arr = pa.array(range(1_000_000))

# Slice: NO data copy, just offset + length adjustment
sliced = arr.slice(500_000, 100_000)  # offset=500K, length=100K

# sliced shares the same underlying buffer
# Only metadata (offset, length) differs
```

```
Original buffer: [0, 1, 2, ..., 999999]
                       ↑ offset=500000, length=100000
Slice view:     ──────[500000, ..., 599999]──────
                  (same physical memory, different logical view)
```

---

## 2. Arrow Memory Model

### Memory Pools & Allocators

```python
import pyarrow as pa

# Check default memory pool
pool = pa.default_memory_pool()
print(f"Backend: {pool.backend_name}")      # jemalloc, mimalloc, or system
print(f"Allocated: {pool.bytes_allocated()}")
print(f"Max memory: {pool.max_memory()}")

# Available pools
print(pa.supported_memory_backends())  # ['jemalloc', 'mimalloc', 'system']

# Use specific pool
jemalloc_pool = pa.jemalloc_memory_pool()
mimalloc_pool = pa.mimalloc_memory_pool()
system_pool = pa.system_memory_pool()

# Logging pool (wraps another pool, tracks allocations)
logging_pool = pa.logging_memory_pool(pa.default_memory_pool())
```

**Pool selection guidance**:
- `jemalloc`: Best for multi-threaded workloads (default on Linux)
- `mimalloc`: Best for Windows, good general purpose
- `system`: malloc/free, useful for debugging

### IPC Format - Stream & File

```
┌─────────────────────────────────────────────────────────────┐
│                   IPC STREAM FORMAT                           │
│                                                               │
│  ┌────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────┐  │
│  │ Schema │→ │RecordBatch 1│→ │RecordBatch 2│→ │  EOS   │  │
│  │Message │  │  Message    │  │  Message    │  │ marker │  │
│  └────────┘  └─────────────┘  └─────────────┘  └────────┘  │
│                                                               │
│  • Forward-only reading                                       │
│  • No random access                                           │
│  • Suitable for pipes, sockets, streaming                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                   IPC FILE FORMAT (.arrow)                    │
│                                                               │
│  ┌──────┐┌────────┐┌─────────┐┌─────────┐┌────────┐┌──────┐│
│  │MAGIC ││ Schema ││ Batch 1 ││ Batch 2 ││ Footer ││MAGIC ││
│  │ARROW1││Message ││         ││         ││(index) ││ARROW1││
│  └──────┘└────────┘└─────────┘└─────────┘└────────┘└──────┘│
│                                                               │
│  • Random access via footer index                             │
│  • Seek to any batch by offset                                │
│  • Suitable for files, memory-mapped I/O                      │
└─────────────────────────────────────────────────────────────┘
```

```python
import pyarrow as pa
import pyarrow.ipc as ipc

# Create sample data
table = pa.table({
    'id': pa.array([1, 2, 3, 4, 5]),
    'name': pa.array(['Alice', 'Bob', 'Charlie', 'Diana', 'Eve']),
    'score': pa.array([95.5, 87.3, 92.1, 88.7, 91.4])
})

# === IPC Stream Format ===
# Write
sink = pa.BufferOutputStream()
writer = ipc.new_stream(sink, table.schema)
writer.write_table(table)
writer.close()
buf = sink.getvalue()

# Read
reader = ipc.open_stream(buf)
read_table = reader.read_all()

# === IPC File Format ===
# Write to file
with pa.OSFile('/tmp/data.arrow', 'wb') as f:
    writer = ipc.new_file(f, table.schema)
    writer.write_table(table)
    writer.close()

# Read from file (random access)
with pa.OSFile('/tmp/data.arrow', 'rb') as f:
    reader = ipc.open_file(f)
    print(f"Num batches: {reader.num_record_batches}")
    batch_0 = reader.get_batch(0)  # Random access!
```

### Memory Mapping

```python
import pyarrow as pa
import pyarrow.ipc as ipc

# Write Arrow IPC file
table = pa.table({'x': pa.array(range(10_000_000))})
with pa.OSFile('/tmp/large.arrow', 'wb') as f:
    writer = ipc.new_file(f, table.schema)
    writer.write_table(table)
    writer.close()

# Memory-map the file (no copy into user space!)
mmap = pa.memory_map('/tmp/large.arrow', 'r')
reader = ipc.open_file(mmap)

# Access data - pages loaded on demand by OS
batch = reader.get_batch(0)
col = batch.column(0)  # Only pages for this column loaded

# Benefits:
# - No explicit read() call needed
# - OS manages page cache
# - Multiple processes can share same physical pages
# - Lazy loading - only accessed pages are faulted in
```

### Shared Memory Zero-Copy (Plasma - deprecated but concept remains)

```
┌─────────────────────────────────────────────────────────────┐
│                 SHARED MEMORY PATTERN                         │
│                                                               │
│  Process A              Shared Memory           Process B     │
│  ┌──────────┐          ┌──────────────┐       ┌──────────┐  │
│  │ Write    │──────────│ Arrow Buffers │───────│  Read    │  │
│  │ Arrow IPC│  mmap    │ (OS managed)  │ mmap  │ Arrow IPC│  │
│  └──────────┘          └──────────────┘       └──────────┘  │
│                                                               │
│  Zero-copy: both processes see same physical memory           │
└─────────────────────────────────────────────────────────────┘
```

Modern approach uses Flight IPC or direct shared memory:

```python
# Using shared memory via IPC (e.g., between Spark and Python worker)
import pyarrow as pa
import pyarrow.ipc as ipc
import mmap
import os

# Writer process
def write_to_shared_memory(table, shm_path):
    # Serialize to IPC stream
    sink = pa.BufferOutputStream()
    writer = ipc.new_stream(sink, table.schema)
    writer.write_table(table)
    writer.close()
    buf = sink.getvalue()
    
    # Write to shared memory file
    fd = os.open(shm_path, os.O_CREAT | os.O_RDWR)
    os.ftruncate(fd, len(buf))
    mm = mmap.mmap(fd, len(buf))
    mm.write(buf)
    mm.close()
    os.close(fd)

# Reader process
def read_from_shared_memory(shm_path):
    mmap_file = pa.memory_map(shm_path, 'r')
    reader = ipc.open_stream(mmap_file)
    return reader.read_all()
```

### GPU (CUDA) Integration

```python
import pyarrow as pa
import pyarrow.cuda as cuda

# Get CUDA context for GPU 0
ctx = cuda.Context(0)

# Allocate GPU buffer
gpu_buf = ctx.new_buffer(1024)

# Copy Arrow buffer to GPU
cpu_arr = pa.array([1, 2, 3, 4, 5], type=pa.int64())
cpu_buf = cpu_arr.buffers()[1]  # Values buffer

gpu_buf = ctx.buffer_from_data(cpu_buf)

# Copy back from GPU
cpu_buf_back = gpu_buf.copy_to_host()

# IPC on GPU - serialize RecordBatch for GPU-to-GPU transfer
batch = pa.record_batch({'x': pa.array(range(1000))})
sink = pa.BufferOutputStream()
writer = ipc.new_stream(sink, batch.schema)
writer.write_batch(batch)
writer.close()

# Transfer IPC message to GPU
ipc_buf = sink.getvalue()
gpu_ipc_buf = ctx.buffer_from_data(ipc_buf)

# On receiving GPU: deserialize directly on device
# (Used by cuDF/RAPIDS for zero-copy GPU-to-GPU)
```

```
┌─────────────────────────────────────────────────────────────┐
│              GPU ARROW DATA PATH                             │
│                                                               │
│  CPU Memory          PCIe/NVLink         GPU Memory          │
│  ┌──────────┐                           ┌──────────┐        │
│  │ Arrow    │──── DMA Transfer ────────→│ Arrow    │        │
│  │ Buffers  │     (cudaMemcpy)          │ Buffers  │        │
│  └──────────┘                           └──────────┘        │
│                                          │                   │
│                                          ▼                   │
│                                    ┌──────────┐              │
│                                    │ cuDF /   │              │
│                                    │ RAPIDS   │              │
│                                    │ Compute  │              │
│                                    └──────────┘              │
│                                                               │
│  GPU-Direct RDMA: NIC → GPU (bypass CPU entirely)            │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Arrow Flight

### What is Flight?

Arrow Flight is a high-performance RPC framework for transferring Arrow data over the network, built on gRPC with Arrow IPC as the wire format.

```
┌─────────────────────────────────────────────────────────────┐
│                    FLIGHT ARCHITECTURE                        │
│                                                               │
│  Client                  Network              Server          │
│  ┌──────────┐           gRPC/HTTP2          ┌──────────┐    │
│  │          │◄─────── bidirectional ────────►│          │    │
│  │ Flight   │          streaming            │ Flight   │    │
│  │ Client   │                               │ Server   │    │
│  │          │  Wire format: Arrow IPC        │          │    │
│  │          │  (no ser/de on either side!)   │          │    │
│  └──────────┘                               └──────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### Flight vs JDBC/ODBC

| Aspect | JDBC/ODBC | Arrow Flight |
|--------|-----------|--------------|
| Wire format | Row-based, text/binary | Arrow IPC (columnar) |
| Serialization | Row → bytes → row | Zero-copy Arrow buffers |
| Parallelism | Single stream | Multiple endpoints (parallel streams) |
| Throughput | ~100-400 MB/s | ~2-5 GB/s (10-100x faster) |
| Data types | Limited (SQL types) | Rich (nested, temporal, decimal) |
| Back-pressure | No | Yes (gRPC flow control) |
| Compression | Per-driver | Built-in (LZ4/ZSTD) |
| Streaming | Cursor-based | Native streaming |
| Metadata | Result set metadata | Rich FlightInfo + app metadata |

**Benchmark numbers** (typical, 10 Gbps network):
- JDBC PostgreSQL: ~150 MB/s
- ODBC SQL Server: ~200 MB/s  
- Arrow Flight: ~3-5 GB/s (saturates 10Gbps NIC with compression)

### RPC Methods

```
┌─────────────────────────────────────────────────────────────┐
│                    FLIGHT RPC METHODS                         │
│                                                               │
│  ┌─────────────────┐                                         │
│  │ ListFlights()   │ → List available datasets               │
│  └─────────────────┘                                         │
│                                                               │
│  ┌─────────────────┐                                         │
│  │ GetFlightInfo() │ → Get metadata + endpoints for dataset  │
│  └─────────────────┘   (schema, size estimate, locations)    │
│          │                                                    │
│          ▼                                                    │
│  ┌─────────────────┐                                         │
│  │ GetSchema()     │ → Get just the schema (lightweight)     │
│  └─────────────────┘                                         │
│                                                               │
│  ┌─────────────────┐                                         │
│  │ DoGet(ticket)   │ → Stream RecordBatches FROM server      │
│  └─────────────────┘   (parallel across endpoints)           │
│                                                               │
│  ┌─────────────────┐                                         │
│  │ DoPut(stream)   │ → Stream RecordBatches TO server        │
│  └─────────────────┘   (upload/ingest)                       │
│                                                               │
│  ┌─────────────────┐                                         │
│  │ DoExchange()    │ → Bidirectional streaming                │
│  └─────────────────┘   (transform, query with streaming I/O) │
│                                                               │
│  ┌─────────────────┐                                         │
│  │ DoAction()      │ → Custom RPC (cancel, health check)     │
│  └─────────────────┘                                         │
└─────────────────────────────────────────────────────────────┘
```

### Parallel Data Retrieval Pattern

```
┌─────────────────────────────────────────────────────────────┐
│              PARALLEL FLIGHT RETRIEVAL                        │
│                                                               │
│  Client                                                       │
│    │                                                          │
│    │─── GetFlightInfo("sales_2024") ───────────► Server      │
│    │◄── FlightInfo {                                         │
│    │      schema: ...,                                        │
│    │      endpoints: [                                        │
│    │        {ticket: "part-0", locations: ["node1:8815"]},   │
│    │        {ticket: "part-1", locations: ["node2:8815"]},   │
│    │        {ticket: "part-2", locations: ["node3:8815"]},   │
│    │      ]                                                   │
│    │    } ──────────────────────────────────────────────      │
│    │                                                          │
│    ├─── DoGet("part-0") ──────────────────────► Node 1       │
│    ├─── DoGet("part-1") ──────────────────────► Node 2       │
│    └─── DoGet("part-2") ──────────────────────► Node 3       │
│                                                               │
│    All streams read in parallel → combine locally             │
└─────────────────────────────────────────────────────────────┘
```

### Flight SQL

Flight SQL extends Flight with SQL semantics:

```
┌─────────────────────────────────────────────────────────────┐
│  Flight SQL = Flight + SQL commands + catalog methods         │
│                                                               │
│  Additional methods:                                          │
│  • GetCatalogs() → list databases                            │
│  • GetSchemas() → list schemas                               │
│  • GetTables() → list tables + columns                       │
│  • CreatePreparedStatement()                                  │
│  • Execute(query) → FlightInfo (then DoGet for results)      │
│  • ExecuteUpdate(DML) → affected row count                   │
└─────────────────────────────────────────────────────────────┘
```

### Python Flight Server & Client Example

```python
import pyarrow as pa
import pyarrow.flight as flight
import pyarrow.parquet as pq


class DataServer(flight.FlightServerBase):
    """Production-quality Flight server example."""
    
    def __init__(self, location="grpc://0.0.0.0:8815", **kwargs):
        super().__init__(location, **kwargs)
        # In production: connect to data source (Parquet, DB, etc.)
        self._tables = {}
        self._load_data()
    
    def _load_data(self):
        """Load sample datasets."""
        self._tables["sales"] = pa.table({
            'date': pa.array(['2024-01-01', '2024-01-02'] * 500000),
            'amount': pa.array([100.0, 200.0] * 500000),
            'region': pa.array(['US', 'EU'] * 500000),
        })
    
    def list_flights(self, context, criteria):
        """List available datasets."""
        for name, table in self._tables.items():
            descriptor = flight.FlightDescriptor.for_path(name)
            info = flight.FlightInfo(
                schema=table.schema,
                descriptor=descriptor,
                endpoints=[
                    flight.FlightEndpoint(
                        ticket=flight.Ticket(name.encode()),
                        locations=[flight.Location.for_grpc_tcp("localhost", 8815)]
                    )
                ],
                total_records=table.num_rows,
                total_bytes=table.nbytes,
            )
            yield info
    
    def get_flight_info(self, context, descriptor):
        """Return metadata for a specific dataset."""
        name = descriptor.path[0].decode()
        if name not in self._tables:
            raise flight.FlightUnavailableError(f"Unknown dataset: {name}")
        
        table = self._tables[name]
        
        # Multiple endpoints for parallel retrieval
        endpoints = []
        num_partitions = 4
        rows_per_partition = table.num_rows // num_partitions
        
        for i in range(num_partitions):
            ticket_data = f"{name}:{i}:{rows_per_partition}".encode()
            endpoints.append(
                flight.FlightEndpoint(
                    ticket=flight.Ticket(ticket_data),
                    locations=[]  # empty = same server
                )
            )
        
        return flight.FlightInfo(
            schema=table.schema,
            descriptor=descriptor,
            endpoints=endpoints,
            total_records=table.num_rows,
            total_bytes=table.nbytes,
        )
    
    def do_get(self, context, ticket):
        """Stream data for a ticket."""
        parts = ticket.ticket.decode().split(":")
        name = parts[0]
        
        if len(parts) == 3:
            # Partitioned request
            partition_idx = int(parts[1])
            partition_size = int(parts[2])
            offset = partition_idx * partition_size
            table = self._tables[name].slice(offset, partition_size)
        else:
            table = self._tables[name]
        
        return flight.RecordBatchStream(table)
    
    def do_put(self, context, descriptor, reader, writer):
        """Receive uploaded data."""
        name = descriptor.path[0].decode()
        table = reader.read_all()
        self._tables[name] = table
        print(f"Received table '{name}': {table.num_rows} rows")
    
    def do_exchange(self, context, descriptor, reader, writer):
        """Bidirectional transform - e.g., filter/aggregate on the fly."""
        # Read request metadata for filter params
        for chunk in reader:
            batch = chunk.data
            # Example: double all amounts
            amounts = batch.column('amount')
            doubled = pa.compute.multiply(amounts, 2)
            new_batch = batch.set_column(
                batch.schema.get_field_index('amount'),
                'amount',
                doubled
            )
            writer.write_batch(new_batch)
    
    def list_actions(self, context):
        return [
            flight.ActionType("healthcheck", "Check server health"),
            flight.ActionType("drop_dataset", "Remove a dataset"),
        ]
    
    def do_action(self, context, action):
        if action.type == "healthcheck":
            yield flight.Result(b'{"status": "healthy"}')
        elif action.type == "drop_dataset":
            name = action.body.to_pybytes().decode()
            if name in self._tables:
                del self._tables[name]
                yield flight.Result(f"Dropped {name}".encode())


# === Authentication Middleware ===
class TokenServerMiddleware(flight.ServerMiddleware):
    def __init__(self, token):
        self.token = token
    
    def sending_headers(self):
        return {}


class TokenServerMiddlewareFactory(flight.ServerMiddlewareFactory):
    def __init__(self, valid_tokens):
        self.valid_tokens = valid_tokens
    
    def start_call(self, info, headers):
        auth_header = headers.get("authorization", [])
        if not auth_header:
            raise flight.FlightUnauthenticatedError("No token")
        token = auth_header[0].replace("Bearer ", "")
        if token not in self.valid_tokens:
            raise flight.FlightUnauthenticatedError("Invalid token")
        return TokenServerMiddleware(token)


# Start server with auth
def start_server():
    middleware = {"auth": TokenServerMiddlewareFactory({"secret-token-123"})}
    server = DataServer(
        location="grpc://0.0.0.0:8815",
        middleware=middleware,
    )
    print("Flight server started on port 8815")
    server.serve()


# === Client ===
class DataClient:
    def __init__(self, host="localhost", port=8815, token=None):
        self.location = flight.Location.for_grpc_tcp(host, port)
        self.client = flight.connect(self.location)
        if token:
            self.client.authenticate_basic_token("", token)
    
    def list_datasets(self):
        """List available flights."""
        for fl in self.client.list_flights():
            print(f"  {fl.descriptor.path}: {fl.total_records} rows, {fl.total_bytes} bytes")
    
    def get_table(self, name):
        """Retrieve full table (parallel)."""
        descriptor = flight.FlightDescriptor.for_path(name)
        info = self.client.get_flight_info(descriptor)
        
        # Read all endpoints (could parallelize with threads)
        batches = []
        for endpoint in info.endpoints:
            reader = self.client.do_get(endpoint.ticket)
            batches.append(reader.read_all())
        
        return pa.concat_tables(batches)
    
    def upload_table(self, name, table):
        """Upload a table to server."""
        descriptor = flight.FlightDescriptor.for_path(name)
        writer, _ = self.client.do_put(descriptor, table.schema)
        writer.write_table(table)
        writer.close()


# Usage
if __name__ == "__main__":
    # In one process:
    # start_server()
    
    # In another:
    client = DataClient()
    client.list_datasets()
    table = client.get_table("sales")
    print(f"Got {table.num_rows} rows at {table.nbytes / 1e6:.1f} MB")
```

### Flight with TLS

```python
# Server with TLS
with open("server.crt", "rb") as f:
    tls_cert = f.read()
with open("server.key", "rb") as f:
    tls_key = f.read()

server = DataServer(
    location="grpc+tls://0.0.0.0:8815",
    tls_certificates=[(tls_cert, tls_key)],
)

# Client with TLS
with open("ca.crt", "rb") as f:
    root_cert = f.read()

client = flight.connect(
    "grpc+tls://server:8815",
    tls_root_certs=root_cert,
)
```

---

## 4. Arrow in Ecosystem

### PyArrow

```python
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
import pyarrow.dataset as ds
import pyarrow.csv as csv
import pyarrow.json as json_reader

# === Core Data Structures ===
# Arrays (1D)
int_arr = pa.array([1, 2, None, 4, 5], type=pa.int64())
str_arr = pa.array(["hello", "world", None])

# Chunked Arrays (logical array, multiple physical chunks)
chunked = pa.chunked_array([
    pa.array([1, 2, 3]),
    pa.array([4, 5, 6]),
])

# Tables (columnar, chunked)
table = pa.table({
    'id': pa.array(range(1000)),
    'value': pa.array([float(x) * 1.5 for x in range(1000)]),
    'category': pa.array(['A', 'B', 'C'] * 333 + ['A']),
})

# === Compute Functions (vectorized, SIMD-accelerated) ===
# Arithmetic
result = pc.add(int_arr, 10)
result = pc.multiply(int_arr, pa.scalar(2))

# Aggregation
pc.sum(int_arr)       # 12
pc.mean(int_arr)      # 3.0
pc.min_max(int_arr)   # {'min': 1, 'max': 5}
pc.count(int_arr)     # 4 (non-null)
pc.stddev(int_arr)    # standard deviation

# Filtering
mask = pc.greater(int_arr, pa.scalar(2))
filtered = pc.filter(int_arr, mask)  # [4, 5]

# Sorting
indices = pc.sort_indices(table, sort_keys=[("value", "descending")])
sorted_table = table.take(indices)

# Group by
grouped = table.group_by("category").aggregate([
    ("value", "sum"),
    ("value", "mean"),
    ("id", "count"),
])

# String operations
names = pa.array(["Alice Smith", "Bob Jones", "Charlie Brown"])
pc.utf8_upper(names)
pc.utf8_split_whitespace(names)
pc.match_substring(names, "Smith")

# === Dataset API (multi-file, partitioned) ===
dataset = ds.dataset(
    "s3://bucket/warehouse/events/",
    format="parquet",
    partitioning=ds.partitioning(
        pa.schema([("year", pa.int32()), ("month", pa.int32())]),
        flavor="hive",  # year=2024/month=01/
    ),
)

# Lazy scan with pushdown
scanner = dataset.scanner(
    columns=["event_type", "user_id", "timestamp"],
    filter=(ds.field("year") == 2024) & (ds.field("month") >= 6),
)
table = scanner.to_table()

# Write partitioned Parquet
ds.write_dataset(
    table,
    "/output/path/",
    format="parquet",
    partitioning=ds.partitioning(pa.schema([("category", pa.utf8())])),
    existing_data_behavior="overwrite_or_ignore",
)
```

### Spark 3.x Integration

```python
from pyspark.sql import SparkSession
from pyspark.sql.functions import pandas_udf
import pandas as pd
import pyarrow as pa

spark = SparkSession.builder \
    .config("spark.sql.execution.arrow.pyspark.enabled", "true") \
    .config("spark.sql.execution.arrow.pyspark.fallback.enabled", "true") \
    .config("spark.sql.execution.arrow.maxRecordsPerBatch", "10000") \
    .getOrCreate()

# === toPandas() with Arrow (10-100x faster) ===
df = spark.range(10_000_000)
pdf = df.toPandas()  # Uses Arrow under the hood when enabled

# === createDataFrame with Arrow ===
pdf = pd.DataFrame({'a': range(1000000), 'b': range(1000000)})
sdf = spark.createDataFrame(pdf)  # Arrow-accelerated

# === Vectorized UDFs (pandas_udf) ===
# Series → Series (map)
@pandas_udf("double")
def multiply_by_two(s: pd.Series) -> pd.Series:
    return s * 2

df = spark.range(1000000).toDF("value")
df.select(multiply_by_two(df.value)).show()

# Series → Scalar (aggregate)
@pandas_udf("double")
def weighted_mean(v: pd.Series, w: pd.Series) -> float:
    return (v * w).sum() / w.sum()

# Iterator of Series → Iterator of Series (map with state)
from typing import Iterator
@pandas_udf("double")
def predict_batch(iterator: Iterator[pd.Series]) -> Iterator[pd.Series]:
    # Load model once
    model = load_model()
    for batch in iterator:
        yield pd.Series(model.predict(batch.values.reshape(-1, 1)))

# Group Map (applyInPandas)
def train_per_group(pdf: pd.DataFrame) -> pd.DataFrame:
    # Full pandas DataFrame per group
    model = fit_model(pdf['features'], pdf['label'])
    pdf['prediction'] = model.predict(pdf['features'])
    return pdf

result = df.groupBy("group_id").applyInPandas(
    train_per_group,
    schema="group_id long, features double, label double, prediction double"
)
```

### Pandas ArrowDtype (Pandas 2.x)

```python
import pandas as pd
import pyarrow as pa

# Use Arrow as Pandas backend (Pandas 2.0+)
df = pd.DataFrame({
    'name': pd.array(['Alice', 'Bob', None, 'Diana'], dtype='string[pyarrow]'),
    'age': pd.array([30, 25, None, 35], dtype='int64[pyarrow]'),
    'score': pd.array([95.5, 87.3, None, 91.2], dtype='float64[pyarrow]'),
    'active': pd.array([True, False, None, True], dtype='bool[pyarrow]'),
})

# Benefits:
# - Native null support (no NaN sentinel)
# - Lower memory usage (no Python object overhead)
# - String operations backed by Arrow compute (faster)
# - Consistent types (no object dtype surprises)

# Read Parquet directly into Arrow-backed DataFrame
df = pd.read_parquet("data.parquet", dtype_backend="pyarrow")

# Convert existing DataFrame
df_arrow = df.convert_dtypes(dtype_backend="pyarrow")
```

### DuckDB Integration

```python
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

# DuckDB ↔ Arrow: zero-copy!
con = duckdb.connect()

# Query Arrow table directly (zero-copy scan)
arrow_table = pa.table({'x': range(10_000_000), 'y': range(10_000_000)})
result = con.execute("SELECT x, sum(y) FROM arrow_table WHERE x > 5000000 GROUP BY x").arrow()

# Result is Arrow table (zero-copy return)
print(type(result))  # <class 'pyarrow.lib.Table'>

# Scan Parquet via Arrow Dataset API
dataset = pq.ParquetDataset("s3://bucket/data/")
result = con.execute("SELECT * FROM dataset WHERE year = 2024").arrow()

# Register Arrow table as view
con.register("my_view", arrow_table)
con.execute("SELECT count(*) FROM my_view").fetchone()

# DuckDB → Arrow → Pandas (all zero-copy where possible)
pandas_df = con.execute("SELECT * FROM 'huge_file.parquet'").df()  # Arrow intermediate
```

### Flink / PyFlink

```python
from pyflink.table import EnvironmentSettings, TableEnvironment
from pyflink.table.udf import udf, udaf, ScalarFunction
from pyflink.common import Row
import pyarrow as pa

# PyFlink uses Arrow for Python UDF data exchange
env_settings = EnvironmentSettings.in_streaming_mode()
t_env = TableEnvironment.create(env_settings)

# Arrow optimization (enabled by default in Flink 1.15+)
t_env.get_config().set("python.fn-execution.arrow.batch.size", "10000")
t_env.get_config().set("python.fn-execution.bundle.size", "100000")

# Vectorized UDF (Arrow-backed)
@udf(result_type='BIGINT', func_type='pandas')
def pandas_add(a, b):
    return a + b  # Operates on pandas Series (Arrow-backed)
```

### DataFusion (Rust)

```rust
// DataFusion: Arrow-native query engine in Rust
use datafusion::prelude::*;
use arrow::array::{Int64Array, StringArray};
use arrow::record_batch::RecordBatch;

#[tokio::main]
async fn main() -> Result<()> {
    let ctx = SessionContext::new();
    
    // Register Parquet file
    ctx.register_parquet("events", "events.parquet", ParquetReadOptions::default()).await?;
    
    // SQL query → Arrow RecordBatches
    let df = ctx.sql("SELECT event_type, COUNT(*) as cnt 
                      FROM events 
                      WHERE timestamp > '2024-01-01' 
                      GROUP BY event_type 
                      ORDER BY cnt DESC").await?;
    
    // Collect results as Arrow batches
    let batches: Vec<RecordBatch> = df.collect().await?;
    
    // DataFrame API
    let df = ctx.read_parquet("events.parquet", ParquetReadOptions::default()).await?
        .filter(col("amount").gt(lit(100)))?
        .aggregate(vec![col("region")], vec![sum(col("amount"))])?;
    
    Ok(())
}
```

### Polars

```python
import polars as pl

# Polars is built on Arrow2 (Rust Arrow implementation)
# All operations are Arrow-native

df = pl.DataFrame({
    "id": range(1_000_000),
    "value": [float(x) * 1.5 for x in range(1_000_000)],
    "group": ["A", "B", "C"] * 333_333 + ["A"],
})

# Lazy evaluation + Arrow-native execution
result = (
    df.lazy()
    .filter(pl.col("value") > 100.0)
    .group_by("group")
    .agg([
        pl.col("value").sum().alias("total"),
        pl.col("value").mean().alias("avg"),
        pl.col("id").count().alias("cnt"),
    ])
    .sort("total", descending=True)
    .collect()
)

# Interop with PyArrow (zero-copy)
arrow_table = df.to_arrow()           # Polars → Arrow (zero-copy)
df_back = pl.from_arrow(arrow_table)  # Arrow → Polars (zero-copy)

# Scan Parquet (lazy, pushdown)
lf = pl.scan_parquet("s3://bucket/data/**/*.parquet")
result = lf.filter(pl.col("year") == 2024).collect()
```

---

## 5. Arrow for Data Engineering Patterns

### Zero-Copy Spark ↔ Python

```
┌─────────────────────────────────────────────────────────────┐
│           SPARK ↔ PYTHON DATA EXCHANGE                       │
│                                                               │
│  JVM (Spark)              Arrow IPC           Python Worker   │
│  ┌──────────────┐        ┌──────────┐       ┌────────────┐  │
│  │ InternalRow  │──────→ │ Arrow    │──────→│ Pandas DF  │  │
│  │ (Tungsten)   │ encode │ Batches  │ zero  │ (Arrow     │  │
│  │              │        │ (IPC     │ copy  │  backend)  │  │
│  │              │◀────── │  stream) │◀──────│            │  │
│  └──────────────┘ decode └──────────┘       └────────────┘  │
│                                                               │
│  Without Arrow: serialize → socket → deserialize (slow)      │
│  With Arrow: columnar encode → shared buffer → zero-copy     │
│                                                               │
│  Speedup: 10-100x for toPandas() / createDataFrame()        │
└─────────────────────────────────────────────────────────────┘
```

### Bridge Streaming and Batch

```python
import pyarrow as pa
import pyarrow.flight as flight
import pyarrow.parquet as pq
from confluent_kafka import Consumer

class StreamToBatchBridge:
    """
    Consume Kafka → accumulate Arrow batches → write Parquet.
    Arrow as the universal intermediate.
    """
    
    def __init__(self, schema, batch_size=100_000, output_path="s3://bucket/output/"):
        self.schema = schema
        self.batch_size = batch_size
        self.output_path = output_path
        self.buffer = {field.name: [] for field in schema}
        self.row_count = 0
    
    def consume_message(self, msg):
        """Add message to Arrow buffer."""
        data = json.loads(msg.value())
        for field in self.schema:
            self.buffer[field.name].append(data.get(field.name))
        self.row_count += 1
        
        if self.row_count >= self.batch_size:
            self.flush()
    
    def flush(self):
        """Convert buffer to Arrow and write Parquet."""
        arrays = []
        for field in self.schema:
            arrays.append(pa.array(self.buffer[field.name], type=field.type))
        
        batch = pa.record_batch(arrays, schema=self.schema)
        table = pa.Table.from_batches([batch])
        
        # Write Parquet (Arrow → Parquet is extremely efficient)
        partition_path = f"{self.output_path}/dt={datetime.now():%Y-%m-%d-%H}/"
        pq.write_table(table, f"{partition_path}/part-{uuid4()}.parquet",
                       compression='zstd', row_group_size=100_000)
        
        # Reset
        self.buffer = {field.name: [] for field in self.schema}
        self.row_count = 0
```

### Flight as Serving Layer

```
┌─────────────────────────────────────────────────────────────┐
│              FLIGHT SERVING ARCHITECTURE                      │
│                                                               │
│  Data Sources          Flight Server          Consumers       │
│                                                               │
│  ┌─────────┐          ┌──────────────┐      ┌──────────┐   │
│  │ Parquet │──scan───→│              │←─────│ Spark    │   │
│  │ (S3)   │          │   Flight     │      │ Jobs     │   │
│  └─────────┘          │   Server    │      └──────────┘   │
│                        │             │                      │
│  ┌─────────┐          │  - Caching  │      ┌──────────┐   │
│  │ Postgres│──query──→│  - AuthZ    │←─────│ ML       │   │
│  │         │          │  - Routing  │      │ Training │   │
│  └─────────┘          │  - Metrics  │      └──────────┘   │
│                        │             │                      │
│  ┌─────────┐          │             │      ┌──────────┐   │
│  │ Kafka   │──stream─→│             │←─────│ Dashboard│   │
│  │         │          │             │      │ (DuckDB) │   │
│  └─────────┘          └──────────────┘      └──────────┘   │
│                                                               │
│  All data exchanged as Arrow - zero serde overhead            │
└─────────────────────────────────────────────────────────────┘
```

### IPC Pipelines (Microservices)

```python
"""
Multi-stage pipeline using Arrow IPC over Unix sockets.
Each stage is a separate process - connected via Arrow IPC streams.
"""
import pyarrow as pa
import pyarrow.ipc as ipc
import socket
import os

# Stage 1: Producer
def stage_ingest(output_socket_path):
    """Read CSV, emit Arrow IPC stream."""
    import pyarrow.csv as csv
    table = csv.read_csv("input.csv")
    
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(output_socket_path)
    
    writer = ipc.new_stream(sock.makefile('wb'), table.schema)
    for batch in table.to_batches(max_chunksize=65536):
        writer.write_batch(batch)
    writer.close()
    sock.close()

# Stage 2: Transform
def stage_transform(input_socket_path, output_socket_path):
    """Read Arrow IPC, transform, emit Arrow IPC."""
    import pyarrow.compute as pc
    
    # Read from upstream
    in_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    in_sock.bind(input_socket_path)
    in_sock.listen(1)
    conn, _ = in_sock.accept()
    reader = ipc.open_stream(conn.makefile('rb'))
    
    # Write to downstream
    out_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    out_sock.connect(output_socket_path)
    
    schema = reader.schema
    writer = ipc.new_stream(out_sock.makefile('wb'), schema)
    
    for batch in reader:
        # Transform: filter rows where amount > 0
        mask = pc.greater(batch.column('amount'), 0)
        filtered = pc.filter(batch, mask)  # Still a RecordBatch
        writer.write_batch(filtered)
    
    writer.close()
```

### Parquet Read Path Optimization

```python
import pyarrow.parquet as pq
import pyarrow as pa

# Optimized Parquet reading with Arrow
parquet_file = pq.ParquetFile("large_dataset.parquet")

# 1. Column pruning (only read needed columns)
table = pq.read_table("data.parquet", columns=["id", "amount", "date"])

# 2. Row group filtering (predicate pushdown)
table = pq.read_table(
    "data.parquet",
    filters=[
        ("date", ">=", "2024-01-01"),
        ("amount", ">", 100),
    ]
)

# 3. Memory-mapped reading (no copy for metadata)
table = pq.read_table("data.parquet", memory_map=True)

# 4. Parallel column reading
table = pq.read_table("data.parquet", use_threads=True)

# 5. Batch reading (streaming, low memory)
for batch in parquet_file.iter_batches(batch_size=100_000, columns=["id", "amount"]):
    process(batch)  # Process each batch without loading full file

# 6. Pre-buffer (async I/O for remote files)
table = pq.read_table("data.parquet", pre_buffer=True, use_threads=True)

# 7. Dataset API for multi-file + partitioned
import pyarrow.dataset as ds
dataset = ds.dataset("s3://bucket/table/", format="parquet", partitioning="hive")
scanner = dataset.scanner(
    columns=["col1", "col2"],
    filter=ds.field("partition_col") == "2024",
    batch_size=2**20,  # 1M rows per batch
    use_threads=True,
    fragment_readahead=4,  # Prefetch 4 fragments
    batch_readahead=16,    # Prefetch 16 batches
)
```

---

## 6. Performance

### SIMD Operations

Arrow's compute kernels leverage SIMD (Single Instruction, Multiple Data):

```
┌─────────────────────────────────────────────────────────────┐
│              SIMD PROCESSING                                  │
│                                                               │
│  Scalar (1 element/instruction):                             │
│  [1] + [10] = [11]  →  [2] + [10] = [12]  →  ...           │
│   1 cycle         1 cycle                                     │
│                                                               │
│  AVX-512 (8 int64 elements/instruction):                     │
│  [1,2,3,4,5,6,7,8] + [10,10,10,10,10,10,10,10]             │
│  = [11,12,13,14,15,16,17,18]                                │
│   1 cycle for 8 elements!                                     │
│                                                               │
│  Arrow's 64-byte alignment enables this:                     │
│  - 64 bytes = 8 × int64 = one AVX-512 register              │
│  - No unaligned access penalties                              │
│  - Validity bitmap processed 64 bits at a time               │
└─────────────────────────────────────────────────────────────┘
```

### Compute Kernels

```python
import pyarrow.compute as pc
import pyarrow as pa
import time

# Arrow compute vs Python loop
arr = pa.array(range(10_000_000), type=pa.int64())

# Arrow compute (SIMD-accelerated)
start = time.time()
result = pc.sum(arr)
arrow_time = time.time() - start  # ~5ms

# Pure Python
start = time.time()
result = sum(range(10_000_000))
python_time = time.time() - start  # ~400ms

# Arrow is ~80x faster for simple aggregations

# Available kernel categories:
# - Arithmetic: add, subtract, multiply, divide, power, negate, abs
# - Comparison: equal, not_equal, greater, less, between
# - Logical: and_, or_, xor, invert
# - String: utf8_upper, utf8_lower, utf8_length, match_substring
# - Temporal: year, month, day, hour, strftime, assume_timezone
# - Aggregation: sum, mean, min_max, count, variance, quantile
# - Set: is_in, index_in, dictionary_encode, unique, value_counts
# - Sort: sort_indices, partition_nth_indices, rank
# - Filter/Take: filter, take, drop_null
# - Cast: cast (type conversion)
```

### Batch Size Tuning

```
┌──────────────────────────────────────────────────────────┐
│            BATCH SIZE TRADE-OFFS                           │
│                                                           │
│  Small batches (1K-10K rows):                            │
│  + Low latency (fast first result)                       │
│  + Low memory per batch                                  │
│  - Higher per-batch overhead                             │
│  - Poor SIMD utilization                                 │
│  → Use for: streaming, interactive queries               │
│                                                           │
│  Medium batches (64K-256K rows):                         │
│  + Good balance latency vs throughput                    │
│  + Good cache utilization                                │
│  → Use for: general ETL, Flight transfers                │
│                                                           │
│  Large batches (1M+ rows):                               │
│  + Maximum throughput                                    │
│  + Best SIMD efficiency                                  │
│  - High latency to first result                          │
│  - Large memory per batch                                │
│  → Use for: batch analytics, bulk loads                  │
│                                                           │
│  Sweet spot for most workloads: 64K-128K rows            │
└──────────────────────────────────────────────────────────┘
```

### Compression

```python
import pyarrow as pa
import pyarrow.ipc as ipc

table = pa.table({'data': pa.array(range(1_000_000))})

# IPC with compression
options = ipc.IpcWriteOptions(compression='zstd')  # or 'lz4'
sink = pa.BufferOutputStream()
writer = ipc.new_stream(sink, table.schema, options=options)
writer.write_table(table)
writer.close()

# Parquet compression
import pyarrow.parquet as pq
pq.write_table(table, "output.parquet", compression='zstd', compression_level=3)
```

| Codec | Ratio | Compress Speed | Decompress Speed | Use Case |
|-------|-------|---------------|-----------------|----------|
| None | 1.0x | N/A | N/A | In-memory, local IPC |
| LZ4 | 2-3x | ~4 GB/s | ~6 GB/s | Flight, streaming (speed) |
| ZSTD (level 1) | 3-4x | ~1.5 GB/s | ~3 GB/s | Flight, balance |
| ZSTD (level 3) | 4-5x | ~800 MB/s | ~3 GB/s | Parquet storage |
| ZSTD (level 9) | 5-7x | ~200 MB/s | ~3 GB/s | Archival Parquet |
| Snappy | 2-3x | ~2 GB/s | ~3 GB/s | Legacy Parquet default |

---

## 7. ADBC (Arrow Database Connectivity)

### What is ADBC?

```
┌─────────────────────────────────────────────────────────────┐
│                    ADBC ARCHITECTURE                          │
│                                                               │
│  Application                                                  │
│  ┌──────────────────────────────────────────┐                │
│  │  ADBC API (language-specific bindings)    │                │
│  └──────────┬───────────────────────────────┘                │
│             │                                                 │
│  ┌──────────▼───────────────────────────────┐                │
│  │  ADBC Driver Manager                      │                │
│  └──────────┬──────────┬───────────┬────────┘                │
│             │          │           │                          │
│  ┌──────────▼──┐ ┌─────▼────┐ ┌───▼──────┐                  │
│  │ PostgreSQL  │ │  SQLite  │ │  Flight  │                  │
│  │   Driver    │ │  Driver  │ │SQL Driver│                  │
│  └──────────┬──┘ └─────┬────┘ └───┬──────┘                  │
│             │          │           │                          │
│  ┌──────────▼──┐ ┌─────▼────┐ ┌───▼──────┐                  │
│  │ PostgreSQL  │ │  SQLite  │ │  Flight  │                  │
│  │  Database   │ │ Database │ │  Server  │                  │
│  └─────────────┘ └──────────┘ └──────────┘                  │
│                                                               │
│  Key: Data returned as Arrow arrays (not row-by-row)         │
└─────────────────────────────────────────────────────────────┘
```

### ADBC vs JDBC/ODBC

| Aspect | JDBC/ODBC | ADBC |
|--------|-----------|------|
| Return format | Rows (ResultSet/cursor) | Arrow RecordBatches |
| Bulk fetch | Row-at-a-time or batch | Columnar batches natively |
| Type system | SQL types → language types | Arrow types (rich, exact) |
| Null handling | isNull() per cell | Validity bitmap (batch) |
| Bulk ingest | INSERT loops or COPY | Native Arrow bulk ingest |
| Nested types | Poor support | Full Arrow type system |
| Memory | Copies at every layer | Zero-copy possible |
| Throughput | ~100-400 MB/s | ~2-5 GB/s |

### Usage

```python
import adbc_driver_postgresql.dbapi as pg_dbapi
import adbc_driver_sqlite.dbapi as sqlite_dbapi
import pyarrow as pa

# PostgreSQL via ADBC
with pg_dbapi.connect("postgresql://localhost/mydb") as conn:
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM events WHERE date > '2024-01-01'")
        
        # Get results as Arrow Table (not row-by-row!)
        table = cursor.fetch_arrow_table()
        print(f"Got {table.num_rows} rows, {table.nbytes / 1e6:.1f} MB")
        
        # Bulk ingest (Arrow → DB, no row-by-row INSERT)
        new_data = pa.table({
            'id': pa.array(range(100_000)),
            'value': pa.array([1.0] * 100_000),
        })
        cursor.adbc_ingest("target_table", new_data, mode="append")
        # Uses COPY protocol under the hood - orders of magnitude faster

# SQLite via ADBC
with sqlite_dbapi.connect("/tmp/test.db") as conn:
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM users")
        table = cursor.fetch_arrow_table()
```

### Bulk Ingestion Performance

```
┌──────────────────────────────────────────────────────────┐
│  Ingesting 1M rows into PostgreSQL:                       │
│                                                           │
│  Method                    Time        Throughput          │
│  ─────────────────────────────────────────────────────    │
│  INSERT (row-by-row)       ~120s       ~8K rows/s         │
│  executemany (batched)     ~30s        ~33K rows/s        │
│  COPY (psycopg2)           ~5s         ~200K rows/s       │
│  ADBC bulk ingest          ~2s         ~500K rows/s       │
│                                                           │
│  ADBC advantage: Arrow columnar → COPY binary protocol    │
│  No intermediate CSV/text conversion                      │
└──────────────────────────────────────────────────────────┘
```

---

## 8. Comparison Tables

### Arrow vs Parquet vs ORC vs Avro

| Feature | Arrow | Parquet | ORC | Avro |
|---------|-------|---------|-----|------|
| **Primary use** | In-memory interchange | Columnar storage | Columnar storage | Row-based storage/RPC |
| **Layout** | Columnar | Columnar | Columnar | Row-based |
| **Compression** | Optional | Required | Required | Optional |
| **Schema evolution** | N/A (ephemeral) | Add/remove columns | Add/remove columns | Full (reader/writer schema) |
| **Encoding** | Dictionary, RLE | Dict, RLE, Delta, Hybrid | Dict, RLE, Delta | None |
| **Nested types** | Full support | Full support | Full support | Full support |
| **Predicate pushdown** | N/A | Row group stats | Stripe stats | No |
| **Splittable** | Per batch | Per row group | Per stripe | Per block |
| **Random access** | O(1) | Per row group | Per stripe | No |
| **Best for** | Inter-process, compute | Data lakes (read-heavy) | Hive/HDFS (write-heavy) | Kafka, schema registry |
| **Ecosystem** | Universal | Spark, Presto, Athena | Hive, Spark | Kafka, Avro RPC |
| **Typical size ratio** | 1.0x (uncompressed) | 0.15-0.25x | 0.15-0.25x | 0.4-0.6x |

### Flight vs JDBC vs ODBC

| Feature | Arrow Flight | JDBC | ODBC |
|---------|-------------|------|------|
| **Wire format** | Arrow IPC (columnar) | Vendor-specific (row) | Vendor-specific (row) |
| **Protocol** | gRPC/HTTP2 | TCP (vendor) | TCP (vendor) |
| **Throughput** | 2-5 GB/s | 100-400 MB/s | 100-400 MB/s |
| **Parallelism** | Multi-endpoint native | Single connection | Single connection |
| **Streaming** | Bidirectional | Forward-only cursor | Forward-only cursor |
| **Back-pressure** | gRPC flow control | None | None |
| **Type fidelity** | Full Arrow types | SQL types | SQL types |
| **Bulk ingest** | DoPut (streaming) | Batch INSERT | Batch INSERT |
| **SQL support** | Flight SQL extension | Native | Native |
| **Encryption** | TLS built-in | Driver-dependent | Driver-dependent |
| **Auth** | Pluggable middleware | Username/password | Username/password |
| **Language support** | C++, Python, Java, Go, Rust | Java (primary) | C/C++ (primary) |
| **Maturity** | Growing (2019+) | Very mature (1997) | Very mature (1992) |
| **Use case** | Analytics, ML, data mesh | OLTP apps, BI tools | Legacy apps, Excel |

### When to Use What

```
┌──────────────────────────────────────────────────────────┐
│  DECISION GUIDE                                           │
│                                                           │
│  Need to store data on disk?                             │
│  ├── Read-heavy analytics → Parquet                      │
│  ├── Write-heavy (Hive) → ORC                           │
│  └── Streaming/messaging → Avro                          │
│                                                           │
│  Need to move data between processes?                    │
│  ├── Same machine → Arrow IPC (shared memory/file)       │
│  ├── Over network, high throughput → Arrow Flight         │
│  └── Need SQL semantics over network → Flight SQL        │
│                                                           │
│  Need to query a database?                               │
│  ├── Analytics workload → ADBC                           │
│  ├── Traditional app → JDBC/ODBC                         │
│  └── Existing Flight SQL server → Flight SQL client      │
│                                                           │
│  Need in-memory processing?                              │
│  ├── Python → PyArrow / Polars / DuckDB                  │
│  ├── Rust → DataFusion / Polars                          │
│  ├── JVM → Arrow Java / Spark                            │
│  └── Multi-language → Arrow C Data Interface             │
└──────────────────────────────────────────────────────────┘
```

---

## 9. Arrow C Data Interface & C Stream Interface

```
┌─────────────────────────────────────────────────────────────┐
│  C DATA INTERFACE - Zero-copy across language boundaries     │
│                                                               │
│  Problem: How do Python, R, Julia share Arrow without copy?  │
│                                                               │
│  struct ArrowArray {                                          │
│    int64_t length;                                           │
│    int64_t null_count;                                       │
│    int64_t offset;                                           │
│    int64_t n_buffers;                                        │
│    int64_t n_children;                                       │
│    const void** buffers;     // pointer to actual data       │
│    struct ArrowArray** children;                              │
│    void (*release)(struct ArrowArray*);  // destructor        │
│  };                                                           │
│                                                               │
│  Just pass pointer → zero-copy across FFI boundary!          │
└─────────────────────────────────────────────────────────────┘
```

```python
# Python ↔ R via C Data Interface (example with DuckDB)
import pyarrow as pa
import duckdb

# PyArrow → DuckDB (zero-copy via C Data Interface)
table = pa.table({'x': [1, 2, 3]})
con = duckdb.connect()
result = con.execute("SELECT * FROM table WHERE x > 1").arrow()
# No serialization! Pointers exchanged via C Data Interface
```

---

## 10. Production Considerations

### Memory Management

```python
import pyarrow as pa

# Monitor memory usage
pool = pa.default_memory_pool()
print(f"Current allocation: {pool.bytes_allocated() / 1e9:.2f} GB")
print(f"Peak allocation: {pool.max_memory() / 1e9:.2f} GB")

# Explicitly release memory
table = pa.table({'x': range(10_000_000)})
del table  # Buffers released when refcount → 0

# For long-running processes, periodically check:
# pool.bytes_allocated() should not grow unbounded
```

### Best Practices Summary

1. **Use Arrow as interchange**, not as a database
2. **Batch sizes**: 64K-128K rows for general processing
3. **Compression**: LZ4 for speed, ZSTD for ratio (Flight/IPC)
4. **Memory mapping**: Use for local file access patterns
5. **Flight**: Use for any inter-service data transfer >10MB
6. **ADBC**: Use for analytics DB access (replaces JDBC in Python)
7. **Dictionary encoding**: Always for low-cardinality string columns
8. **Column pruning**: Always specify only needed columns
9. **Schema**: Define explicitly, don't rely on inference in production
10. **Monitoring**: Track `bytes_allocated()` in long-running services

---

## References

- Apache Arrow Specification: https://arrow.apache.org/docs/format/
- Arrow Flight RPC: https://arrow.apache.org/docs/format/Flight.html
- PyArrow API: https://arrow.apache.org/docs/python/
- ADBC: https://arrow.apache.org/adbc/
- Arrow Columnar Format: https://arrow.apache.org/docs/format/Columnar.html
