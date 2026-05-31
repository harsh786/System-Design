# Problem 123: Design Service Discovery & Registry

## Problem Statement

Design a Service Discovery and Registry system similar to Consul, Eureka, or etcd-based discovery. The system should enable microservices to find and communicate with each other dynamically without hardcoded endpoints, handling the constantly changing topology of cloud-native environments.

## Key Challenges

### 1. Service Registration
- Self-registration vs third-party registration patterns
- Registration metadata (version, region, capabilities, weight)
- Lease-based registration with TTL
- Graceful deregistration on shutdown

### 2. Health Checking
- Active health checks (platform polls services)
- Passive health checks (based on real traffic success/failure)
- Health check types: TCP, HTTP, gRPC, script-based
- Cascading health (marking unhealthy if critical dependency is down)

### 3. Discovery Patterns
- DNS-based discovery (SRV records, A records)
- Client-side discovery (client queries registry, load balances)
- Server-side discovery (load balancer queries registry)
- Trade-offs between each approach

### 4. Stale Registration Handling
- Detecting zombie instances (registered but not serving)
- Expiry and eviction policies
- Protecting against mass expiry during network partitions

### 5. Multi-Datacenter Support
- Cross-datacenter service discovery
- Locality-aware routing (prefer local instances)
- WAN replication strategies
- Split-brain handling

### 6. Consistency vs Availability Trade-off
- CP model (strong consistency, potential unavailability during partitions)
- AP model (always available, potentially stale data)
- Choosing the right model for discovery vs configuration

## Scale Requirements
- 100K+ service instances registered
- Millions of discovery lookups per second
- Sub-100ms registration propagation
- 99.999% availability (discovery is on the critical path)
- Multi-region deployment

## Expected Design Areas
- Registry data model and storage
- Health check subsystem
- Replication and consistency protocol
- DNS integration layer
- Client SDK design
- Failure handling and partition tolerance
