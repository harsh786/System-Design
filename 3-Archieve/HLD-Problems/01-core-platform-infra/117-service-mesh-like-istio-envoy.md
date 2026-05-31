# Problem 117: Design a Service Mesh (like Istio/Envoy)

## Problem Statement

Design a service mesh infrastructure that provides transparent networking capabilities
to microservices without requiring application code changes. The mesh should handle
service-to-service communication, security, and observability at the infrastructure layer.

## Key Challenges

1. **Sidecar Proxy Architecture**: Deploy and manage sidecar proxies alongside every
   service instance with minimal latency overhead and resource consumption.
2. **mTLS Between Services**: Automatic mutual TLS for all inter-service communication
   with certificate rotation and identity-based authentication.
3. **Traffic Management**: Support canary deployments, traffic mirroring, fault injection,
   retries, and timeouts configured declaratively.
4. **Observability**: Distributed tracing integration, metrics collection (latency, error
   rates, throughput), and access logging without application instrumentation.
5. **Control Plane vs Data Plane**: Separate configuration management (control plane)
   from request processing (data plane) with efficient config propagation.
6. **Service Discovery Integration**: Integrate with multiple service registries and
   support dynamic endpoint updates with health checking.
7. **Rate Limiting Per Service Pair**: Enforce rate limits on specific service-to-service
   communication paths with distributed counters.
8. **Circuit Breaking**: Detect unhealthy upstream services and fail fast to prevent
   cascade failures across the mesh.

## Scale Requirements

- 10,000+ microservices in the mesh
- Millions of requests per second across the mesh
- Sub-millisecond added latency per hop from sidecar proxies
- Configuration propagation to all sidecars within seconds
- Support for multiple clusters and multi-tenancy
- Zero-downtime upgrades of mesh infrastructure

## Expected Discussion Areas

- xDS protocol for configuration distribution
- Envoy filter chains and extension mechanisms
- Certificate authority and SPIFFE identity framework
- Horizontal scaling of control plane components
- Graceful degradation when control plane is unavailable
