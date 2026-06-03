# etcd - Real World Use Cases & Production Guide

## Core Concepts

etcd is a distributed, strongly consistent key-value store used for shared configuration, service discovery, and coordination in distributed systems.

```
┌─────────────────────────────────────────────────────────┐
│                    etcd Architecture                      │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐          │
│  │  Client  │    │  Client  │    │  Client  │          │
│  └────┬─────┘    └────┬─────┘    └────┬─────┘          │
│       │               │               │                  │
│       └───────────────┼───────────────┘                  │
│                       │ gRPC API                         │
│       ┌───────────────┼───────────────┐                  │
│       ▼               ▼               ▼                  │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐             │
│  │  Node 1 │◄──►│  Node 2 │◄──►│  Node 3 │             │
│  │(Leader) │    │(Follower)│    │(Follower)│             │
│  └────┬────┘    └────┬────┘    └────┬────┘             │
│       │               │               │                  │
│  ┌────┴────┐    ┌────┴────┐    ┌────┴────┐             │
│  │   WAL   │    │   WAL   │    │   WAL   │             │
│  │ +Snap   │    │ +Snap   │    │ +Snap   │             │
│  └─────────┘    └─────────┘    └─────────┘             │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Key Properties

| Property | Description |
|----------|-------------|
| **MVCC** | Multi-Version Concurrency Control - every key has a revision history |
| **Raft Consensus** | All writes go through leader, replicated to majority |
| **Watches** | Event-driven change notification (no polling) |
| **Leases** | TTL-based key expiration for heartbeating |
| **Transactions** | Atomic compare-and-swap (mini-transactions) |
| **Linearizable** | Reads reflect most recent committed write |
| **WAL + Snapshot** | Write-Ahead Log for durability, snapshots for compaction |
| **gRPC API** | High-performance binary protocol |

### Performance Characteristics

```
Typical Performance (3-node cluster, SSD):
┌─────────────────────────────────────────┐
│ Sequential writes:  ~10,000-30,000 ops/s │
│ Concurrent writes:  ~50,000-100,000 ops/s│
│ Linearizable reads: ~50,000-80,000 ops/s │
│ Serializable reads: ~100,000-150,000 ops/s│
│ Watch throughput:   ~100,000 events/s     │
│ P99 write latency:  2-10ms               │
│ P99 read latency:   1-5ms                │
│ Max recommended keys: ~1 million          │
│ Max value size:      1.5 MB               │
│ Max DB size:         8 GB (default)       │
└─────────────────────────────────────────┘
```

---

## Use Case 1: Kubernetes Control Plane

Kubernetes uses etcd as its **single source of truth** for all cluster state. Every pod, service, deployment, configmap, and secret is stored in etcd.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Kubernetes Control Plane                   │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   kubectl    │  │  Controller  │  │  Scheduler   │      │
│  │              │  │   Manager    │  │              │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                  │                  │              │
│         ▼                  ▼                  ▼              │
│  ┌─────────────────────────────────────────────────┐        │
│  │              kube-apiserver                       │        │
│  │  ┌─────────┐  ┌──────────┐  ┌───────────────┐  │        │
│  │  │  REST   │  │  Watch   │  │  Admission    │  │        │
│  │  │ Handler │  │  Cache   │  │  Controllers  │  │        │
│  │  └────┬────┘  └────┬─────┘  └───────────────┘  │        │
│  │       │             │                            │        │
│  │       ▼             ▼                            │        │
│  │  ┌──────────────────────────┐                   │        │
│  │  │    etcd3 Storage Layer   │                   │        │
│  │  └────────────┬─────────────┘                   │        │
│  └───────────────┼─────────────────────────────────┘        │
│                  │                                            │
│                  ▼                                            │
│  ┌──────────────────────────────────────────────┐           │
│  │              etcd Cluster (3 or 5)            │           │
│  │                                               │           │
│  │  ┌────────┐    ┌────────┐    ┌────────┐     │           │
│  │  │ etcd-0 │◄──►│ etcd-1 │◄──►│ etcd-2 │     │           │
│  │  │(Leader)│    │        │    │        │     │           │
│  │  └────────┘    └────────┘    └────────┘     │           │
│  └──────────────────────────────────────────────┘           │
│                                                              │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │   kubelet  │  │   kubelet  │  │   kubelet  │            │
│  │  (node-1)  │  │  (node-2)  │  │  (node-3)  │            │
│  └────────────┘  └────────────┘  └────────────┘            │
└─────────────────────────────────────────────────────────────┘
```

### Key Space Design

```
/registry/
├── pods/
│   └── {namespace}/
│       └── {pod-name}              # Pod spec + status
├── services/
│   ├── specs/
│   │   └── {namespace}/{svc-name}  # Service definition
│   └── endpoints/
│       └── {namespace}/{svc-name}  # Endpoint IPs
├── deployments/
│   └── {namespace}/{deploy-name}   # Deployment spec
├── configmaps/
│   └── {namespace}/{cm-name}       # ConfigMap data
├── secrets/
│   └── {namespace}/{secret-name}   # Encrypted secrets
├── namespaces/
│   └── {namespace-name}            # Namespace metadata
├── nodes/
│   └── {node-name}                 # Node status + capacity
├── leases/
│   └── kube-system/
│       └── {leader-identity}       # Leader election leases
└── events/
    └── {namespace}/{event-name}    # Cluster events
```

### Watch Patterns

```go
// API server watches all resources for its informer cache
// Watch prefix /registry/pods/ for ALL pod changes
watcher := client.Watch(ctx, "/registry/pods/", clientv3.WithPrefix())

// Controller Manager watches specific resources
// e.g., ReplicaSet controller watches pods with label selectors
watcher := client.Watch(ctx, "/registry/pods/default/",
    clientv3.WithPrefix(),
    clientv3.WithRev(lastKnownRevision),  // Resume from revision
    clientv3.WithProgressNotify(),         // Heartbeat for stale watches
)

// Scheduler watches unscheduled pods
// Filters via API server, but etcd provides the watch stream
for event := range watchChan {
    switch event.Type {
    case mvccpb.PUT:
        // New/updated pod - check if needs scheduling
    case mvccpb.DELETE:
        // Pod deleted - free resources
    }
}
```

### Lease Usage

```go
// Node heartbeat - kubelet reports node alive via lease
lease, _ := client.Grant(ctx, 40) // 40-second TTL

// kubelet keeps the lease alive
client.Put(ctx, "/registry/leases/kube-node-lease/node-1",
    leaseData, clientv3.WithLease(lease.ID))

// Renew every 10s (lease renewal interval)
keepAliveCh, _ := client.KeepAlive(ctx, lease.ID)

// If kubelet stops renewing, after 40s:
//   - Node marked NotReady
//   - Pods evicted after pod-eviction-timeout
```

### Scale Requirements

| Metric | Small Cluster | Large Cluster |
|--------|--------------|---------------|
| Nodes | 3 etcd | 5 etcd |
| K8s Nodes | <100 | 5000+ |
| Pods | <1000 | 150,000+ |
| Keys in etcd | ~10,000 | ~1,000,000 |
| DB Size | <200MB | 2-8GB |
| Watch connections | ~100 | ~10,000 |
| Write QPS | ~500 | ~5,000 |

---

## Use Case 2: CoreDNS / Service Discovery

CoreDNS uses etcd as a backend for dynamic DNS records, enabling service discovery in cloud-native environments.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│               CoreDNS + etcd Service Discovery               │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐               │
│  │  Service  │  │  Service  │  │  Service  │               │
│  │  App-A    │  │  App-B    │  │  App-C    │               │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘               │
│        │               │               │                     │
│        │  DNS Query     │  Register     │  DNS Query         │
│        ▼               ▼               ▼                     │
│  ┌─────────────────────────────────────────────────┐        │
│  │                 CoreDNS Cluster                   │        │
│  │                                                   │        │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐       │        │
│  │  │ CoreDNS  │  │ CoreDNS  │  │ CoreDNS  │       │        │
│  │  │   :53    │  │   :53    │  │   :53    │       │        │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘       │        │
│  │       │              │              │             │        │
│  │       │   etcd plugin (watch)       │             │        │
│  │       └──────────────┼──────────────┘             │        │
│  └──────────────────────┼────────────────────────────┘        │
│                         │                                     │
│                         ▼                                     │
│  ┌──────────────────────────────────────────────┐            │
│  │              etcd Cluster                     │            │
│  │                                               │            │
│  │  /skydns/com/example/svc-a  → {"host":"..."}  │            │
│  │  /skydns/com/example/svc-b  → {"host":"..."}  │            │
│  │  /skydns/io/prod/api        → {"host":"..."}  │            │
│  └──────────────────────────────────────────────┘            │
│                         ▲                                     │
│                         │                                     │
│  ┌──────────────────────┴───────────────────────┐            │
│  │          Service Registrar / Registrator      │            │
│  │   (watches containers, registers DNS entries) │            │
│  └──────────────────────────────────────────────┘            │
└─────────────────────────────────────────────────────────────┘
```

### Key Space Design

CoreDNS uses a **reversed domain hierarchy** (SkyDNS convention):

```
/skydns/                              # Root prefix
├── com/
│   └── example/
│       ├── api/
│       │   ├── x1  → {"host":"10.0.1.1","port":8080,"priority":10}
│       │   └── x2  → {"host":"10.0.1.2","port":8080,"priority":10}
│       ├── web/
│       │   └── x1  → {"host":"10.0.2.1","port":443}
│       └── db/
│           ├── master → {"host":"10.0.3.1","port":5432,"priority":10}
│           └── slave  → {"host":"10.0.3.2","port":5432,"priority":20}
├── io/
│   └── prod/
│       └── cache/
│           ├── node1 → {"host":"10.1.1.1","port":6379}
│           └── node2 → {"host":"10.1.1.2","port":6379}
└── local/
    └── cluster/
        └── svc/
            └── default/
                └── kubernetes → {"host":"10.96.0.1","port":443}

# DNS query: api.example.com → lookup /skydns/com/example/api/*
# Returns A records for all children
```

### Watch Patterns

```go
// CoreDNS etcd plugin watches for DNS record changes
// Watches the entire /skydns/ prefix for real-time updates
watcher := client.Watch(ctx, "/skydns/", clientv3.WithPrefix())

for resp := range watcher {
    for _, event := range resp.Events {
        switch event.Type {
        case mvccpb.PUT:
            // New or updated service endpoint
            // Invalidate DNS cache, serve new record
            record := parseSkyDNSRecord(event.Kv.Value)
            dnsCache.Set(keyToDomain(event.Kv.Key), record)
        case mvccpb.DELETE:
            // Service deregistered
            dnsCache.Delete(keyToDomain(event.Kv.Key))
        }
    }
}

// Service registrar adds entries with lease for auto-cleanup
lease, _ := client.Grant(ctx, 30) // 30s TTL
client.Put(ctx, "/skydns/com/example/api/instance-abc",
    `{"host":"10.0.1.5","port":8080}`,
    clientv3.WithLease(lease.ID))
```

### Lease Usage

```go
// Each service instance registers with a lease
// If the service crashes, the DNS record auto-expires

func registerService(client *clientv3.Client, service, host string, port int) {
    lease, _ := client.Grant(ctx, 15)  // 15-second TTL

    key := fmt.Sprintf("/skydns/com/example/%s/%s", service, hostID)
    val := fmt.Sprintf(`{"host":"%s","port":%d}`, host, port)

    client.Put(ctx, key, val, clientv3.WithLease(lease.ID))

    // Keep alive - renew every 5s
    ch, _ := client.KeepAlive(ctx, lease.ID)
    go func() {
        for range ch {
            // Lease renewed successfully
        }
        // Channel closed = lease expired or revoked
        log.Warn("Service lease expired, re-registering...")
    }()
}
```

### Scale Requirements

| Metric | Typical |
|--------|---------|
| etcd nodes | 3 |
| DNS records | 1,000 - 50,000 |
| Watch connections | 10-50 (CoreDNS instances) |
| Updates/sec | 10-500 (service churn) |
| DB size | <100MB |
| DNS query rate | 10,000-100,000 qps (served from CoreDNS cache) |

---

## Use Case 3: Patroni PostgreSQL HA

Patroni uses etcd for **leader election** and **cluster coordination** to provide automatic failover for PostgreSQL clusters.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│              Patroni PostgreSQL HA with etcd                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                      Application Layer                    │   │
│  │   ┌─────────┐    ┌─────────┐    ┌─────────┐            │   │
│  │   │  App 1  │    │  App 2  │    │  App 3  │            │   │
│  │   └────┬────┘    └────┬────┘    └────┬────┘            │   │
│  │        └──────────────┼──────────────┘                   │   │
│  │                       ▼                                   │   │
│  │              ┌────────────────┐                           │   │
│  │              │   HAProxy /    │                           │   │
│  │              │   PgBouncer    │                           │   │
│  │              └───────┬────────┘                           │   │
│  └──────────────────────┼───────────────────────────────────┘   │
│                         │                                        │
│  ┌──────────────────────┼───────────────────────────────────┐   │
│  │                      ▼         PostgreSQL Cluster          │   │
│  │  ┌─────────────────────────────────────────────────┐     │   │
│  │  │                                                  │     │   │
│  │  │  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │   │
│  │  │  │   Node 1     │  │   Node 2     │  │   Node 3   │ │   │
│  │  │  │ ┌──────────┐ │  │ ┌──────────┐ │  │ ┌────────┐│ │   │
│  │  │  │ │ Patroni  │ │  │ │ Patroni  │ │  │ │Patroni ││ │   │
│  │  │  │ └────┬─────┘ │  │ └────┬─────┘ │  │ └───┬────┘│ │   │
│  │  │  │      │        │  │      │        │  │     │     │ │   │
│  │  │  │ ┌────┴─────┐ │  │ ┌────┴─────┐ │  │ ┌───┴───┐│ │   │
│  │  │  │ │PostgreSQL │ │  │ │PostgreSQL │ │  │ │PgSQL  ││ │   │
│  │  │  │ │ (PRIMARY) │ │  │ │ (REPLICA) │ │  │ │(REPL) ││ │   │
│  │  │  │ └──────────┘ │  │ └──────────┘ │  │ └───────┘│ │   │
│  │  │  └──────────────┘  └──────────────┘  └──────────┘ │   │
│  │  └──────────────────────────────────────────────────────┘     │
│  └──────────────────────┬───────────────────────────────────┘   │
│                         │  Heartbeat / Leader Lock                │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    etcd Cluster                            │   │
│  │                                                           │   │
│  │   ┌────────┐      ┌────────┐      ┌────────┐            │   │
│  │   │ etcd-1 │◄────►│ etcd-2 │◄────►│ etcd-3 │            │   │
│  │   └────────┘      └────────┘      └────────┘            │   │
│  │                                                           │   │
│  │   Keys:                                                   │   │
│  │   /service/pg-cluster/leader    = "node1" (lease: 30s)   │   │
│  │   /service/pg-cluster/members/  = [node1, node2, node3]  │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Key Space Design

```
/service/{cluster-name}/
├── leader                    # Current leader (held with lease)
│   Value: "node1"
│   Lease: 30s TTL
│
├── initialize                # Cluster initialization flag
│   Value: "system-id"
│
├── config                    # Dynamic cluster configuration
│   Value: {"ttl":30,"loop_wait":10,"retry_timeout":10,
│            "postgresql":{"parameters":{"max_connections":100}}}
│
├── members/
│   ├── node1                 # Member registration
│   │   Value: {"conn_url":"postgres://10.0.1.1:5432/postgres",
│   │           "api_url":"http://10.0.1.1:8008/patroni",
│   │           "state":"running","role":"master",
│   │           "timeline":3,"xlog_location":"0/5000000"}
│   ├── node2
│   │   Value: {"conn_url":"postgres://10.0.1.2:5432/postgres",
│   │           "state":"running","role":"replica",
│   │           "lag":0}
│   └── node3
│       Value: {...}
│
├── optime/
│   └── leader               # Leader's WAL position (for replicas)
│       Value: "83886080"
│
├── failover                  # Manual failover request
│   Value: {"leader":"node1","candidate":"node2"}
│
└── sync                      # Synchronous replication state
    Value: {"leader":"node1","sync_standby":"node2"}
```

### Watch Patterns

```python
# Patroni watches for leadership changes
def watch_leader(self):
    # Watch the leader key for changes
    watch_id = self.client.watch("/service/pg-cluster/leader")

    for event in watch_id:
        if event.type == "DELETE":
            # Leader key expired! Attempt to become leader
            self.attempt_leader_election()
        elif event.type == "PUT":
            new_leader = event.value
            if new_leader != self.my_name:
                # Someone else became leader, ensure I'm a replica
                self.demote_to_replica(new_leader)

# HAProxy watches for role changes to update routing
def watch_members(self):
    for event in self.client.watch_prefix("/service/pg-cluster/members/"):
        member = json.loads(event.value)
        if member["role"] == "master":
            self.update_primary_backend(member["conn_url"])
        else:
            self.update_replica_backend(member["conn_url"])
```

### Lease Usage

```python
# Leader election via lease - the CORE of Patroni's HA

class PatroniLeader:
    def __init__(self, client, cluster_name, node_name):
        self.ttl = 30  # Leader TTL
        self.loop_wait = 10  # Check interval

    def attempt_leader_election(self):
        # Create a lease
        lease = self.client.lease(ttl=self.ttl)

        # Try to create the leader key (only succeeds if key doesn't exist)
        success = self.client.transaction(
            compare=[
                self.client.transactions.create("/service/pg-cluster/leader") == 0
            ],
            success=[
                self.client.transactions.put(
                    "/service/pg-cluster/leader",
                    self.node_name,
                    lease=lease
                )
            ],
            failure=[]
        )

        if success:
            # I am the leader! Promote PostgreSQL to primary
            self.promote_to_primary()
            self.keep_leader_alive(lease)

    def keep_leader_alive(self, lease):
        """Renew lease every loop_wait seconds"""
        while self.is_healthy():
            lease.refresh()  # Resets TTL to 30s
            time.sleep(self.loop_wait)

        # If PostgreSQL is unhealthy, stop renewing
        # Lease expires after 30s → triggers failover
```

### Failover Sequence

```
Timeline: Leader Failure and Automatic Failover
═══════════════════════════════════════════════════

T=0s    Node1 (Primary) crashes
        - Patroni on Node1 stops renewing lease

T=10s   Lease TTL counting down (30s - 10s = 20s remaining)
        Node2, Node3 still see Node1 as leader

T=30s   Leader lease EXPIRES in etcd
        - etcd deletes /service/pg-cluster/leader
        - Watch fires on Node2 and Node3

T=30.1s Node2 and Node3 both attempt leader election
        - Transaction: IF leader key not exists, THEN put my name
        - Only ONE succeeds (etcd transaction is atomic)

T=30.2s Node2 wins election
        - Node2 promotes PostgreSQL to primary
        - Node2 updates member info: role=master
        - Node3 follows new primary

T=31s   HAProxy detects role change via Patroni REST API
        - Routes writes to Node2

Total failover time: ~30-35 seconds
```

### Scale Requirements

| Metric | Typical |
|--------|---------|
| etcd nodes | 3 |
| PostgreSQL clusters managed | 1-100 per etcd cluster |
| Keys per PG cluster | ~10-20 |
| Write frequency | Every loop_wait (10s) per node |
| Total writes/sec | <50 |
| Lease renewals/sec | ~10-30 |
| DB size | <10MB |

---

## Use Case 4: Vitess Topology Store

Vitess uses etcd as its **topology service** to store MySQL cluster metadata, shard mappings, and tablet (instance) information.

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                 Vitess with etcd Topology Store                    │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                       │
│  │  App 1   │  │  App 2   │  │  App 3   │                       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                       │
│       └──────────────┼──────────────┘                             │
│                      ▼                                            │
│  ┌──────────────────────────────────┐                            │
│  │            VTGate                 │  (Query Router)            │
│  │  - Routes queries to correct     │                            │
│  │    shard/tablet                   │                            │
│  │  - Watches topology for changes  │                            │
│  └──────────────┬───────────────────┘                            │
│                 │                                                  │
│    ┌────────────┼────────────────────┐                           │
│    ▼            ▼                    ▼                            │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐                │
│  │VTTablet│  │VTTablet│  │VTTablet│  │VTTablet│                │
│  │Shard -80│  │Shard -80│  │Shard 80-│  │Shard 80-│               │
│  │(Master) │  │(Replica)│  │(Master) │  │(Replica)│               │
│  │  MySQL  │  │  MySQL  │  │  MySQL  │  │  MySQL  │               │
│  └────┬───┘  └────┬───┘  └────┬───┘  └────┬───┘               │
│       └────────────┴────────────┴────────────┘                    │
│                         │                                         │
│                         ▼  Topology Updates                       │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │                    etcd Cluster                            │    │
│  │                                                           │    │
│  │   Global Topology:        Local (Cell) Topology:          │    │
│  │   /vitess/global/         /vitess/zone1/                  │    │
│  │                                                           │    │
│  │   ┌────────┐  ┌────────┐  ┌────────┐                    │    │
│  │   │ etcd-1 │  │ etcd-2 │  │ etcd-3 │                    │    │
│  │   └────────┘  └────────┘  └────────┘                    │    │
│  └──────────────────────────────────────────────────────────┘    │
│                         ▲                                         │
│                         │                                         │
│  ┌──────────────────────┴───────────────────────────────────┐    │
│  │              VTOrc (Orchestrator)                          │    │
│  │  - Monitors replication                                   │    │
│  │  - Performs automated failover                            │    │
│  │  - Updates topology in etcd                               │    │
│  └──────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

### Key Space Design

```
/vitess/global/                           # Cross-cell metadata
├── keyspaces/
│   ├── commerce/                         # Keyspace definition
│   │   └── Keyspace                      # {"sharding_column":"customer_id"}
│   └── lookup/
│       └── Keyspace
├── shards/
│   ├── commerce/-80/                     # Shard [-inf, 0x80)
│   │   └── Shard                         # {"master_alias":{"cell":"zone1","uid":100}}
│   └── commerce/80-/                     # Shard [0x80, +inf)
│       └── Shard
├── tablets/
│   ├── zone1-0000000100/                 # Tablet (vttablet instance)
│   │   └── Tablet                        # {"hostname":"mysql-1","port":3306,
│   │                                     #  "keyspace":"commerce","shard":"-80",
│   │                                     #  "type":"MASTER"}
│   ├── zone1-0000000101/
│   │   └── Tablet                        # type: "REPLICA"
│   └── zone1-0000000200/
│       └── Tablet                        # shard: "80-", type: "MASTER"
├── cells/
│   ├── zone1/                            # Cell (datacenter) info
│   │   └── CellInfo                      # {"server_address":"etcd-zone1:2379",
│   │                                     #  "root":"/vitess/zone1"}
│   └── zone2/
│       └── CellInfo
└── vschema/
    └── commerce                          # Sharding schema (vindex definitions)

/vitess/zone1/                            # Cell-local topology
├── tablets/
│   ├── zone1-0000000100/
│   │   └── Tablet                        # Local copy for fast reads
│   └── zone1-0000000101/
│       └── Tablet
└── srv_keyspace/
    └── commerce/                         # Serving data (shard map for VTGate)
        └── SrvKeyspace                   # Partition info for query routing
```

### Watch Patterns

```go
// VTGate watches SrvKeyspace for shard routing changes
func (vtgate *VTGate) watchSrvKeyspace(cell, keyspace string) {
    key := fmt.Sprintf("/vitess/%s/srv_keyspace/%s/SrvKeyspace", cell, keyspace)

    watcher := client.Watch(ctx, key)
    for resp := range watcher {
        for _, event := range resp.Events {
            srvKeyspace := &topodatapb.SrvKeyspace{}
            proto.Unmarshal(event.Kv.Value, srvKeyspace)
            // Update query routing table
            vtgate.updateRoutingRules(keyspace, srvKeyspace)
        }
    }
}

// VTOrc watches all tablets for health changes
func (vtorc *VTOrc) watchTablets() {
    watcher := client.Watch(ctx, "/vitess/global/tablets/",
        clientv3.WithPrefix())

    for resp := range watcher {
        for _, event := range resp.Events {
            tablet := parseTablet(event.Kv.Value)
            if tablet.Type == "MASTER" && event.Type == mvccpb.DELETE {
                // Master tablet lost! Initiate failover
                vtorc.initiateFailover(tablet.Keyspace, tablet.Shard)
            }
        }
    }
}
```

### Lease Usage

```go
// VTTablet registers itself with a lease for liveness
func (tablet *VTTablet) register(client *clientv3.Client) {
    lease, _ := client.Grant(ctx, 30)

    tabletPath := fmt.Sprintf("/vitess/%s/tablets/%s/Tablet",
        tablet.Cell, tablet.Alias)
    tabletData, _ := proto.Marshal(tablet.ToProto())

    client.Put(ctx, tabletPath, string(tabletData),
        clientv3.WithLease(lease.ID))

    // Keep alive
    client.KeepAlive(ctx, lease.ID)
}

// VTOrc uses lease for its own leader election
// Only one VTOrc instance is active at a time
func (vtorc *VTOrc) electLeader() {
    session, _ := concurrency.NewSession(client, concurrency.WithTTL(15))
    election := concurrency.NewElection(session, "/vitess/global/vtorc/leader")
    election.Campaign(ctx, vtorc.hostname)
}
```

### Scale Requirements

| Metric | Typical |
|--------|---------|
| etcd nodes | 3 (per cell) + 3 (global) |
| Keyspaces | 10-100 |
| Shards total | 100-10,000 |
| Tablets (MySQL instances) | 500-50,000 |
| Keys in etcd | 1,000-100,000 |
| Watch connections | 50-500 (VTGates + VTTablets) |
| Write frequency | Low (topology changes are rare) |
| DB size | 10-500MB |

---

## Use Case 5: Rook/Ceph Orchestration

Rook uses etcd (indirectly via Kubernetes/etcd) to orchestrate Ceph distributed storage clusters on Kubernetes.

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│            Rook-Ceph on Kubernetes (etcd-backed)                  │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │                  Kubernetes Control Plane                  │    │
│  │                                                           │    │
│  │  ┌────────────────┐     ┌─────────────────────────┐     │    │
│  │  │  kube-apiserver │◄───►│    etcd (3 or 5 nodes)  │     │    │
│  │  └───────┬────────┘     └─────────────────────────┘     │    │
│  │          │                                                │    │
│  └──────────┼────────────────────────────────────────────────┘    │
│             │                                                     │
│  ┌──────────┼────────────────────────────────────────────────┐   │
│  │          ▼              Rook Operator                       │   │
│  │  ┌──────────────────────────────────────────────┐         │   │
│  │  │            Rook Operator Pod                   │         │   │
│  │  │                                               │         │   │
│  │  │  - Watches CephCluster CRDs                   │         │   │
│  │  │  - Reconciles desired vs actual state         │         │   │
│  │  │  - Creates/manages Ceph daemon pods           │         │   │
│  │  │  - Stores config in ConfigMaps/Secrets        │         │   │
│  │  └──────────────┬────────────────────────────────┘         │   │
│  └─────────────────┼─────────────────────────────────────────┘   │
│                    │                                               │
│  ┌─────────────────┼─────────────────────────────────────────┐   │
│  │                 ▼          Ceph Cluster Pods                │   │
│  │                                                            │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐                  │   │
│  │  │  MON-a  │  │  MON-b  │  │  MON-c  │  (Monitors)      │   │
│  │  └─────────┘  └─────────┘  └─────────┘                  │   │
│  │                                                            │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐    │   │
│  │  │  OSD-0  │  │  OSD-1  │  │  OSD-2  │  │  OSD-3  │    │   │
│  │  │ (disk1) │  │ (disk2) │  │ (disk3) │  │ (disk4) │    │   │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘    │   │
│  │                                                            │   │
│  │  ┌─────────┐  ┌─────────┐                                │   │
│  │  │  MDS-a  │  │  MDS-b  │  (Metadata Servers - CephFS)  │   │
│  │  └─────────┘  └─────────┘                                │   │
│  │                                                            │   │
│  │  ┌─────────┐  ┌─────────┐                                │   │
│  │  │  RGW-a  │  │  RGW-b  │  (RADOS Gateway - S3/Swift)   │   │
│  │  └─────────┘  └─────────┘                                │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                   │
│  State stored in etcd (via K8s API):                             │
│  /registry/rook-ceph.io/cephclusters/...                         │
│  /registry/configmaps/rook-ceph/rook-ceph-mon-endpoints          │
│  /registry/secrets/rook-ceph/rook-ceph-admin-keyring             │
└──────────────────────────────────────────────────────────────────┘
```

### Key Space Design (in etcd via Kubernetes)

```
# Rook stores state as Kubernetes resources, which live in etcd:

/registry/
├── rook-ceph.io/
│   ├── cephclusters/
│   │   └── rook-ceph/my-cluster      # CephCluster CR spec
│   ├── cephblockpools/
│   │   └── rook-ceph/replicapool     # Block pool config
│   ├── cephfilesystems/
│   │   └── rook-ceph/myfs            # CephFS config
│   └── cephobjectstores/
│       └── rook-ceph/my-store        # RGW config
│
├── apps/deployments/rook-ceph/
│   ├── rook-ceph-operator           # Operator deployment
│   ├── rook-ceph-mon-a              # Monitor deployments
│   ├── rook-ceph-mon-b
│   ├── rook-ceph-mon-c
│   ├── rook-ceph-mgr-a              # Manager
│   ├── rook-ceph-mds-myfs-a         # MDS
│   └── rook-ceph-rgw-my-store-a     # RGW
│
├── configmaps/rook-ceph/
│   ├── rook-ceph-mon-endpoints      # Mon IPs for cluster
│   │   Value: {"data":{"mapping":"...","maxMonId":"2",
│   │           "csi-cluster-config-json":"[{\"clusterID\":\"...\",
│   │           \"monitors\":[\"10.0.1.1:6789\",...]}]"}}
│   ├── rook-ceph-config              # Ceph.conf equivalent
│   └── rook-config-override          # User overrides
│
├── secrets/rook-ceph/
│   ├── rook-ceph-admin-keyring       # Admin auth key
│   ├── rook-ceph-mon                 # Monitor shared secret
│   └── rook-csi-cephfs-node          # CSI credentials
│
└── persistentvolumes/
    ├── pvc-abc123                     # Ceph RBD volume
    └── pvc-def456                     # CephFS volume
```

### Watch Patterns

```go
// Rook Operator controller-runtime reconciliation loop
// Uses K8s informers which watch etcd under the hood

func (r *CephClusterReconciler) SetupWithManager(mgr ctrl.Manager) error {
    return ctrl.NewControllerManagedBy(mgr).
        For(&cephv1.CephCluster{}).         // Watch CephCluster CRD changes
        Owns(&appsv1.Deployment{}).          // Watch owned Deployments
        Owns(&corev1.Service{}).             // Watch owned Services
        Owns(&corev1.ConfigMap{}).           // Watch owned ConfigMaps
        Watches(&corev1.Node{},             // Watch node changes (new disks)
            handler.EnqueueRequestsFromMapFunc(r.nodeChanged)).
        Complete(r)
}

// Under the hood, this creates etcd watches like:
// Watch /registry/rook-ceph.io/cephclusters/ (prefix)
// Watch /registry/apps/deployments/rook-ceph/ (prefix)
// Watch /registry/nodes/ (prefix, for OSD placement)

func (r *CephClusterReconciler) Reconcile(ctx context.Context,
    req ctrl.Request) (ctrl.Result, error) {

    cluster := &cephv1.CephCluster{}
    r.Client.Get(ctx, req.NamespacedName, cluster)

    // Ensure correct number of MONs
    r.reconcileMonitors(cluster)
    // Ensure OSDs on available disks
    r.reconcileOSDs(cluster)
    // Ensure MDS for CephFS
    r.reconcileMDS(cluster)

    return ctrl.Result{RequeueAfter: 60 * time.Second}, nil
}
```

### Lease Usage

```go
// Rook operator leader election uses Kubernetes Leases (stored in etcd)
// Only one operator instance is active at a time

// /registry/leases/rook-ceph/rook-ceph-operator
// {
//   "holderIdentity": "rook-operator-pod-abc",
//   "leaseDurationSeconds": 137,
//   "acquireTime": "2024-01-15T10:00:00Z",
//   "renewTime": "2024-01-15T10:05:30Z"
// }

// OSD liveness - each OSD pod has a liveness probe
// If OSD pod dies, K8s detects and Rook reconciles
// The pod deletion triggers a watch event in etcd

// Mon quorum tracking - stored in ConfigMap
// If a mon is lost, Rook detects via watch and replaces it
```

### Scale Requirements

| Metric | Typical |
|--------|---------|
| etcd nodes | 3-5 (shared with K8s) |
| Ceph MONs | 3-5 |
| OSDs | 10-1000+ |
| K8s resources for Rook | 100-5000 |
| Watch connections | 10-50 (operator + CSI) |
| Reconciliation frequency | Event-driven + 60s requeue |
| etcd DB impact | 10-100MB additional |

---

## Replication

### Raft Consensus Algorithm

```
┌──────────────────────────────────────────────────────────────┐
│                    Raft State Machine                          │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  Node States:                                                 │
│                                                               │
│  ┌───────────┐    election timeout    ┌───────────┐          │
│  │           │ ─────────────────────► │           │          │
│  │ FOLLOWER  │                        │ CANDIDATE │          │
│  │           │ ◄───────────────────── │           │          │
│  └───────────┘    discovers leader    └─────┬─────┘          │
│       ▲                                     │                 │
│       │           receives majority votes   │                 │
│       │                                     ▼                 │
│       │                              ┌───────────┐           │
│       │                              │           │           │
│       └───────────────────────────── │  LEADER   │           │
│            discovers higher term     │           │           │
│                                      └───────────┘           │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### Leader Election Process

```
Election Timeline:
══════════════════════════════════════════════════════════════

Term 1: Node-A is leader
─────────────────────────────────────────────────────────────
  Node-A: [LEADER]──heartbeat──heartbeat──heartbeat──╳ (crash)
  Node-B: [FOLLOWER]───────────────────────────────────────
  Node-C: [FOLLOWER]───────────────────────────────────────

Term 2: Election triggered (150-300ms random timeout)
─────────────────────────────────────────────────────────────
  Node-A: [DOWN]
  Node-B: [FOLLOWER]──timeout──[CANDIDATE]─RequestVote─►
  Node-C: [FOLLOWER]────────────────────────◄─VoteGranted

  Node-B: [CANDIDATE]──receives 2/3 votes──[LEADER]
  Node-C: [FOLLOWER]──────────────────────────────────

Term 2: Node-B is new leader
─────────────────────────────────────────────────────────────
  Node-A: [DOWN]
  Node-B: [LEADER]──heartbeat──heartbeat──heartbeat──►
  Node-C: [FOLLOWER]──────────────────────────────────
```

### Log Replication Flow

```
Write Request: PUT /key "value"
══════════════════════════════════════════════════════════════

     Client          Leader (A)        Follower (B)      Follower (C)
       │                 │                  │                 │
  1.   │──PUT /key──────►│                  │                 │
       │                 │                  │                 │
  2.   │                 │──AppendEntries──►│                 │
       │   PROPOSE       │──AppendEntries──────────────────►│
       │                 │                  │                 │
  3.   │                 │◄──Success────────│                 │
       │   APPEND        │◄──Success───────────────────────│
       │                 │                  │                 │
  4.   │                 │  (majority=2/3 confirmed)         │
       │   COMMIT        │  Mark entry COMMITTED             │
       │                 │                  │                 │
  5.   │                 │──Commit Index───►│                 │
       │   APPLY         │──Commit Index──────────────────►│
       │                 │                  │                 │
  6.   │◄──OK───────────│  Apply to state machine           │
       │                 │                  │                 │

Log State After Commit:
┌─────────────────────────────────────────────────┐
│  Index:  │ 1 │ 2 │ 3 │ 4 │ 5 │ 6 │ 7 │        │
│  Term:   │ 1 │ 1 │ 1 │ 2 │ 2 │ 2 │ 2 │        │
│  Entry:  │SET│SET│DEL│SET│SET│SET│SET│        │
│  Status: │ C │ C │ C │ C │ C │ C │ P │        │
│          │   │   │   │   │   │   │   │        │
│  C = Committed    P = Pending                   │
└─────────────────────────────────────────────────┘
```

### Learner Nodes (Non-Voting Members)

```
┌─────────────────────────────────────────────────────────┐
│              Learner Node (Non-Voting)                    │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Voting Members:          Learner:                       │
│  ┌────────┐               ┌────────┐                    │
│  │  A     │──replicate───►│  D     │                    │
│  │(Leader)│               │(Learner)│                    │
│  └────────┘               └────────┘                    │
│  ┌────────┐                                             │
│  │  B     │  Learner properties:                        │
│  └────────┘  - Receives log entries                     │
│  ┌────────┐  - Does NOT vote in elections               │
│  │  C     │  - Does NOT count for quorum                │
│  └────────┘  - Can be promoted to voting member         │
│              - Used for safe cluster expansion           │
│                                                          │
│  Use cases:                                             │
│  1. Adding a new node (catch up before voting)          │
│  2. Cross-region read replicas                          │
│  3. Backup/analytics nodes                              │
└─────────────────────────────────────────────────────────┘
```

### Joint Consensus for Membership Changes

```
Safely adding Node-D to a 3-node cluster:
═══════════════════════════════════════════

Phase 1: Joint Configuration [A,B,C] + [A,B,C,D]
──────────────────────────────────────────────────
  Quorum requires majority of BOTH:
  - Old config [A,B,C]: need 2/3
  - New config [A,B,C,D]: need 3/4

Phase 2: New Configuration [A,B,C,D]
──────────────────────────────────────────────────
  Quorum requires majority of new:
  - [A,B,C,D]: need 3/4

This prevents split-brain during transitions.
```

### Snapshot and Compaction

```
┌─────────────────────────────────────────────────────────┐
│            WAL + Snapshot Lifecycle                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  WAL (Write-Ahead Log):                                 │
│  ┌───┬───┬───┬───┬───┬───┬───┬───┬───┬───┐            │
│  │ 1 │ 2 │ 3 │ 4 │ 5 │ 6 │ 7 │ 8 │ 9 │10 │  entries  │
│  └───┴───┴───┴───┴───┴───┴───┴───┴───┴───┘            │
│                                                          │
│  After snapshot at index 7:                             │
│  ┌─────────────────────┐ ┌───┬───┬───┐                 │
│  │    Snapshot (idx 7)  │ │ 8 │ 9 │10 │  remaining WAL │
│  │  (full state dump)   │ └───┴───┴───┘                 │
│  └─────────────────────┘                                │
│                                                          │
│  Compaction (MVCC revision cleanup):                    │
│  Before: key "/foo" has revisions [1, 3, 5, 7, 9]      │
│  Compact(revision=7): removes [1, 3, 5]                 │
│  After:  key "/foo" has revisions [7, 9]                │
│                                                          │
│  Schedule:                                              │
│  - Snapshot: every 10,000 applied entries (default)     │
│  - Compaction: periodic (hourly) or revision-based      │
│  - Defrag: manual, reclaims free pages in boltdb       │
└─────────────────────────────────────────────────────────┘
```

---

## Scalability

### Recommended Cluster Sizes

```
┌─────────────────────────────────────────────────────────────┐
│ Cluster Size │ Fault Tolerance │ Use Case                    │
├──────────────┼─────────────────┼─────────────────────────────┤
│     1        │     0 failures  │ Development/testing only    │
│     3        │     1 failure   │ Standard production (most)  │
│     5        │     2 failures  │ High availability critical  │
│     7        │     3 failures  │ Rarely needed, higher       │
│              │                 │ latency due to quorum size  │
└─────────────────────────────────────────────────────────────┘

Formula: Tolerates (N-1)/2 failures
  3 nodes: majority = 2, tolerates 1 failure
  5 nodes: majority = 3, tolerates 2 failures
  7 nodes: majority = 4, tolerates 3 failures

WARNING: Even numbers (4, 6) provide NO benefit over N-1:
  4 nodes: majority = 3, tolerates 1 failure (same as 3!)
  6 nodes: majority = 4, tolerates 2 failures (same as 5!)
```

### Read/Write Performance Characteristics

```
Write Path (always through leader):
┌────────┐    ┌────────┐    ┌────────┐
│ Client │───►│ Leader │───►│Follower│  (replicate to majority)
└────────┘    └────────┘    └────────┘
                              ▼
              Latency = network RTT + fsync(WAL)
              Typical: 2-10ms (SSD), 20-50ms (HDD)

Read Path:
┌──────────────────────────────────────────────────────────┐
│                                                           │
│  Linearizable Read (default, strong consistency):        │
│  Client ──► Leader ──► confirm leadership ──► respond    │
│  - Must verify leader hasn't been superseded             │
│  - ReadIndex or LeaseRead optimization                   │
│  - Latency: ~2-5ms                                       │
│                                                           │
│  Serializable Read (eventual consistency):               │
│  Client ──► Any Node ──► respond from local state        │
│  - May return stale data                                 │
│  - No leader confirmation needed                         │
│  - Latency: <1ms                                         │
│  - Use for read-heavy, staleness-tolerant workloads      │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

### Watch Mechanism

```
Traditional Polling vs etcd Watch:
═══════════════════════════════════

Polling (BAD):                    Watch (GOOD):
┌────────┐    ┌──────┐           ┌────────┐    ┌──────┐
│ Client │───►│ etcd │           │ Client │◄───│ etcd │
│        │◄───│      │           │        │    │      │
│ (every │    │      │           │(gRPC   │    │      │
│  100ms)│    │      │           │ stream)│    │      │
└────────┘    └──────┘           └────────┘    └──────┘

- N clients polling = N * (1/interval) requests/sec
- Watches: event-driven, near-zero idle cost
- Watch multiplexing: single gRPC stream, multiple watches
- Resume from revision: no missed events after reconnect

Watch internals:
┌──────────────────────────────────────────────────┐
│ mvcc.watchableStore                              │
│                                                  │
│  ┌──────────┐     ┌──────────────────┐          │
│  │  synced  │     │   Event FIFO     │          │
│  │ watchers │◄────│   (per watcher)  │──► gRPC  │
│  └──────────┘     └──────────────────┘   stream │
│       ▲                                          │
│       │ new write committed                      │
│  ┌────┴──────┐                                   │
│  │ unsynced  │  (catching up from old revision)  │
│  │ watchers  │                                   │
│  └───────────┘                                   │
└──────────────────────────────────────────────────┘
```

### Why NOT to Use etcd as a General-Purpose DB

```
┌─────────────────────────────────────────────────────────────┐
│                    etcd is NOT for:                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Large values (max 1.5MB per key)                        │
│  2. Large datasets (recommended <8GB total)                 │
│  3. High write throughput (all writes serialize via leader) │
│  4. Range queries / filtering (no secondary indexes)        │
│  5. Complex queries (no query language)                     │
│  6. Storing blobs, media, logs                              │
│  7. Time-series data                                        │
│  8. Millions of keys (performance degrades)                 │
│                                                              │
│  etcd IS for:                                               │
│  - Small metadata (<1M keys, <8GB)                          │
│  - Configuration / feature flags                            │
│  - Service discovery / registration                         │
│  - Leader election / distributed locks                      │
│  - Watch-heavy workloads (event notification)               │
│  - Strong consistency requirements                          │
└─────────────────────────────────────────────────────────────┘
```

### Comparison: etcd vs ZooKeeper vs Consul

```
┌──────────────────┬───────────────┬───────────────┬──────────────┐
│ Feature          │ etcd          │ ZooKeeper     │ Consul       │
├──────────────────┼───────────────┼───────────────┼──────────────┤
│ Consensus        │ Raft          │ ZAB (Paxos)   │ Raft         │
│ API              │ gRPC + HTTP   │ Custom TCP     │ HTTP + DNS   │
│ Watch            │ Prefix-based  │ Per-node       │ Blocking     │
│                  │ (multiplexed) │ (one-shot)     │ queries      │
│ Data Model       │ Flat KV +     │ Hierarchical   │ KV + Service │
│                  │ prefix ranges │ (ZNodes)       │ catalog      │
│ Max Value Size   │ 1.5 MB        │ 1 MB           │ 512 KB       │
│ Consistency      │ Linearizable  │ Sequential     │ Eventually / │
│                  │               │ (+ sync)       │ Consistent   │
│ Lease/Ephemeral  │ Leases (TTL)  │ Ephemeral      │ Sessions     │
│                  │               │ nodes          │ (TTL)        │
│ Language         │ Go            │ Java           │ Go           │
│ Write perf       │ ~10-50K ops/s │ ~10-50K ops/s  │ ~5-20K ops/s │
│ Read perf        │ ~50-150K ops/s│ ~50-100K ops/s │ ~20-50K ops/s│
│ Service Mesh     │ No            │ No             │ Yes (Connect)│
│ Health Checks    │ No            │ No             │ Yes (built-in│
│ Multi-DC         │ No (single)   │ No (observers) │ Yes (WAN)    │
│ K8s Integration  │ Native        │ Possible       │ Helm chart   │
│ Operational      │ Simple        │ Complex (JVM,  │ Moderate     │
│ Complexity       │               │ GC tuning)     │              │
├──────────────────┼───────────────┼───────────────┼──────────────┤
│ Best for         │ K8s, pure     │ Legacy Java    │ Multi-DC     │
│                  │ coordination  │ ecosystems,    │ service mesh,│
│                  │               │ Kafka, Hadoop  │ service      │
│                  │               │               │ discovery    │
└──────────────────┴───────────────┴───────────────┴──────────────┘
```

---

## Production Setup

### Hardware Requirements

```
┌──────────────────────────────────────────────────────────────┐
│              Minimum Production Hardware                       │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  CPU:    2-4 cores (dedicated, not shared)                    │
│  RAM:    8 GB minimum (etcd caches entire dataset in memory) │
│  Disk:   50 GB SSD (NVMe preferred)                          │
│  Network: 1 Gbps+ (low latency between peers)               │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  *** SSD IS CRITICAL ***                                 │ │
│  │                                                          │ │
│  │  etcd performance is bounded by disk fsync latency:      │ │
│  │                                                          │ │
│  │  NVMe SSD:  fsync ~0.1-0.5ms  → 10K-30K writes/sec     │ │
│  │  SATA SSD:  fsync ~0.5-2ms    → 5K-15K writes/sec      │ │
│  │  HDD:       fsync ~5-20ms     → 500-2K writes/sec      │ │
│  │  Network:   fsync ~2-10ms     → 1K-5K writes/sec       │ │
│  │  (EBS/NFS)                     (AVOID for WAL!)          │ │
│  │                                                          │ │
│  │  The WAL (Write-Ahead Log) must be on fast local SSD.   │ │
│  │  Network-attached storage adds latency to EVERY write.  │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  Large Cluster (>1000 K8s nodes):                            │
│  CPU:    8-16 cores                                          │
│  RAM:    16-64 GB                                            │
│  Disk:   200 GB NVMe SSD                                     │
│  Network: 10 Gbps                                            │
│                                                               │
│  Anti-patterns:                                              │
│  - Running etcd on same disk as other I/O-heavy workloads   │
│  - Using network-attached storage for WAL                    │
│  - Colocating etcd with CPU-intensive processes             │
│  - Insufficient RAM (causes swap, kills performance)        │
└──────────────────────────────────────────────────────────────┘
```

### TLS Configuration

```yaml
# etcd peer (inter-node) TLS
etcd:
  peer-transport-security:
    cert-file: /etc/etcd/pki/peer.crt
    key-file: /etc/etcd/pki/peer.key
    client-cert-auth: true
    trusted-ca-file: /etc/etcd/pki/ca.crt

  # Client TLS
  client-transport-security:
    cert-file: /etc/etcd/pki/server.crt
    key-file: /etc/etcd/pki/server.key
    client-cert-auth: true
    trusted-ca-file: /etc/etcd/pki/ca.crt

# Generate certificates:
# 1. Create CA
#    cfssl gencert -initca ca-csr.json | cfssljson -bare ca
#
# 2. Generate peer certs (one per node)
#    cfssl gencert -ca=ca.pem -ca-key=ca-key.pem \
#      -config=ca-config.json -profile=peer \
#      peer-csr.json | cfssljson -bare peer
#
# 3. Generate server cert
#    cfssl gencert -ca=ca.pem -ca-key=ca-key.pem \
#      -config=ca-config.json -profile=server \
#      server-csr.json | cfssljson -bare server
#
# 4. Generate client cert
#    cfssl gencert -ca=ca.pem -ca-key=ca-key.pem \
#      -config=ca-config.json -profile=client \
#      client-csr.json | cfssljson -bare client
```

### Auth and RBAC

```bash
# Enable authentication
etcdctl auth enable

# Create root user (required)
etcdctl user add root --new-user-password="secret"
etcdctl user grant-role root root

# Create roles
etcdctl role add read-only
etcdctl role grant-permission read-only read "" --prefix  # read all

etcdctl role add kube-apiserver
etcdctl role grant-permission kube-apiserver readwrite /registry/ --prefix

etcdctl role add patroni
etcdctl role grant-permission patroni readwrite /service/ --prefix

# Create users with roles
etcdctl user add kube --new-user-password="kube-pass"
etcdctl user grant-role kube kube-apiserver

etcdctl user add patroni --new-user-password="patroni-pass"
etcdctl user grant-role patroni patroni
```

### Compaction and Defragmentation

```bash
# Auto-compaction (recommended)
# Revision-based: keep last 1000 revisions
etcd --auto-compaction-mode=revision --auto-compaction-retention=1000

# Time-based: keep last 1 hour
etcd --auto-compaction-mode=periodic --auto-compaction-retention=1h

# Manual compaction
REVISION=$(etcdctl endpoint status --write-out=json | jq '.[0].Status.header.revision')
etcdctl compact $REVISION

# Defragmentation (reclaim disk space after compaction)
# WARNING: blocks the member during defrag, run one node at a time
etcdctl defrag --endpoints=https://etcd-1:2379
etcdctl defrag --endpoints=https://etcd-2:2379
etcdctl defrag --endpoints=https://etcd-3:2379

# Check DB size before/after
etcdctl endpoint status --write-out=table
# +----------+--------+---------+---------+-----------+-------+--------+
# | ENDPOINT | DB SIZE| VERSION | LEADER  | RAFT TERM | INDEX | ERRORS |
# +----------+--------+---------+---------+-----------+-------+--------+
```

### Backup and Restore

```bash
# Snapshot backup (run on one member)
etcdctl snapshot save /backup/etcd-$(date +%Y%m%d-%H%M%S).db \
  --endpoints=https://etcd-1:2379 \
  --cacert=/etc/etcd/pki/ca.crt \
  --cert=/etc/etcd/pki/client.crt \
  --key=/etc/etcd/pki/client.key

# Verify snapshot
etcdctl snapshot status /backup/etcd-20240115-100000.db --write-out=table

# Restore (disaster recovery - all members)
# 1. Stop all etcd members
# 2. Restore on each member with unique names/URLs:

etcdctl snapshot restore /backup/etcd-20240115-100000.db \
  --name etcd-1 \
  --initial-cluster "etcd-1=https://10.0.1.1:2380,etcd-2=https://10.0.1.2:2380,etcd-3=https://10.0.1.3:2380" \
  --initial-advertise-peer-urls https://10.0.1.1:2380 \
  --data-dir /var/lib/etcd-restored

# 3. Start all members with restored data directory
# 4. Verify cluster health
etcdctl endpoint health --cluster
```

### Monitoring

```
Key Prometheus Metrics:
═══════════════════════════════════════════════════════════════

Server Health:
  etcd_server_has_leader                    # 1 = healthy, 0 = problem
  etcd_server_leader_changes_seen_total     # Frequent changes = instability
  etcd_server_proposals_failed_total        # Non-zero = cluster issues
  etcd_server_proposals_committed_total     # Write throughput indicator

Disk Performance (CRITICAL):
  etcd_disk_wal_fsync_duration_seconds      # Must be <10ms, ideally <2ms
  etcd_disk_backend_commit_duration_seconds # BoltDB commit time
  etcd_mvcc_db_total_size_in_bytes          # DB size (alert if >6GB)
  etcd_mvcc_db_total_size_in_use_in_bytes   # Actual data (vs allocated)

Network:
  etcd_network_peer_round_trip_time_seconds # Peer latency
  etcd_network_peer_sent_failures_total     # Network issues

gRPC:
  grpc_server_handled_total                 # Request count by method
  grpc_server_handling_seconds              # Request latency

Alerting Rules:
┌─────────────────────────────────────────────────────────────┐
│ CRITICAL: etcd_server_has_leader == 0 for 1m                │
│ CRITICAL: etcd_disk_wal_fsync_duration_seconds_bucket > 10ms│
│ WARNING:  etcd_mvcc_db_total_size_in_bytes > 6GB            │
│ WARNING:  etcd_server_leader_changes_seen_total increase > 3│
│           in 1 hour                                          │
│ WARNING:  etcd_network_peer_round_trip_time > 100ms         │
│ WARNING:  etcd_server_proposals_failed_total increasing      │
└─────────────────────────────────────────────────────────────┘
```

### Disaster Recovery Procedures

```
Scenario 1: Single Node Failure (cluster still has quorum)
═══════════════════════════════════════════════════════════
1. Remove failed member:
   etcdctl member remove <member-id>
2. Provision new node
3. Add new member:
   etcdctl member add etcd-new --peer-urls=https://new-ip:2380
4. Start etcd on new node with --initial-cluster-state=existing

Scenario 2: Quorum Lost (majority of nodes down)
═══════════════════════════════════════════════════
Option A: Wait for nodes to recover (if possible)
Option B: Force new cluster from surviving member:
  1. Stop surviving member
  2. etcd --force-new-cluster --data-dir=/var/lib/etcd
  3. Add new members back one by one

Scenario 3: Total Data Loss (all nodes gone)
═══════════════════════════════════════════════════
1. Get latest snapshot from backup
2. Restore on all new nodes (see Backup section)
3. Verify data integrity
4. Point clients to new cluster

Scenario 4: Data Corruption
═══════════════════════════════════════════════════
1. Identify corrupted member (check logs for checksum errors)
2. Remove corrupted member
3. Add fresh member (it will replicate from healthy peers)
4. If all members corrupted: restore from snapshot backup
```

### Production Configuration Example

```yaml
# /etc/etcd/etcd.conf.yaml
name: etcd-1
data-dir: /var/lib/etcd
wal-dir: /var/lib/etcd/wal    # Separate WAL dir on fastest disk

listen-peer-urls: https://0.0.0.0:2380
listen-client-urls: https://0.0.0.0:2379
advertise-client-urls: https://10.0.1.1:2379
initial-advertise-peer-urls: https://10.0.1.1:2380

initial-cluster: >-
  etcd-1=https://10.0.1.1:2380,
  etcd-2=https://10.0.1.2:2380,
  etcd-3=https://10.0.1.3:2380
initial-cluster-state: new
initial-cluster-token: my-etcd-cluster

# Performance tuning
heartbeat-interval: 100        # ms (default 100)
election-timeout: 1000         # ms (default 1000)
snapshot-count: 10000          # entries before snapshot
quota-backend-bytes: 8589934592  # 8GB max DB size

# Auto-compaction
auto-compaction-mode: periodic
auto-compaction-retention: "1h"

# TLS
client-transport-security:
  cert-file: /etc/etcd/pki/server.crt
  key-file: /etc/etcd/pki/server.key
  client-cert-auth: true
  trusted-ca-file: /etc/etcd/pki/ca.crt

peer-transport-security:
  cert-file: /etc/etcd/pki/peer.crt
  key-file: /etc/etcd/pki/peer.key
  client-cert-auth: true
  trusted-ca-file: /etc/etcd/pki/ca.crt

# Logging
logger: zap
log-level: warn
log-outputs: [stderr, /var/log/etcd/etcd.log]
```

---

## Summary

```
┌──────────────────────────────────────────────────────────────────┐
│                  etcd Decision Framework                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Use etcd when you need:                                         │
│  ✓ Strong consistency (linearizable reads/writes)                │
│  ✓ Watch-based change notification                               │
│  ✓ Leader election / distributed locking                         │
│  ✓ Small metadata store (<1M keys, <8GB)                         │
│  ✓ Kubernetes-native ecosystem                                   │
│                                                                   │
│  Do NOT use etcd when you need:                                  │
│  ✗ Large dataset storage (use a real database)                   │
│  ✗ High write throughput >100K ops/s (use Redis/Cassandra)       │
│  ✗ Complex queries (use PostgreSQL/MongoDB)                      │
│  ✗ Multi-datacenter replication (use Consul or CockroachDB)      │
│  ✗ Large values >1.5MB (use object storage)                      │
│                                                                   │
│  Golden Rules:                                                   │
│  1. Always use SSDs for etcd (NVMe preferred)                    │
│  2. 3 nodes for most; 5 for critical HA                          │
│  3. Monitor etcd_disk_wal_fsync_duration religiously             │
│  4. Set up automated snapshots (hourly minimum)                  │
│  5. Keep DB size under control (compact + defrag)                │
│  6. Never run more than 7 nodes (diminishing returns)            │
│  7. Separate etcd from other workloads                           │
└──────────────────────────────────────────────────────────────────┘
```
