# Linux, OS, and Infrastructure Internals

Production incidents often require understanding the layers below application code. This track prepares you for deep debugging discussions involving Linux, networking, containers, process behavior, and resource limits.

## Architect-Level Outcome

You should be able to reason about how operating-system and infrastructure behavior affects latency, throughput, reliability, and failure modes.

## Linux Process and Thread Basics

Must know:

- Process vs thread.
- Virtual memory.
- File descriptors.
- Signals.
- Context switches.
- Scheduling.
- System calls.
- User mode vs kernel mode.
- Copy-on-write.
- Page cache.
- cgroups and namespaces.

Interview examples:

- Too many open files causes connection failures.
- CPU throttling in Kubernetes increases latency.
- Page cache can make disk reads appear fast until memory pressure.
- Context switching can dominate when thread pools are oversized.

## File Descriptors and Connections

Every socket is a file descriptor.

Failure symptoms:

- `too many open files`.
- connection reset.
- accept failures.
- elevated latency.

Controls:

- `ulimit`.
- connection pooling.
- keepalive settings.
- load balancer idle timeout.
- graceful shutdown.
- leak detection.

## I/O Internals

Key concepts:

- Page cache.
- fsync.
- buffered vs direct I/O.
- random vs sequential I/O.
- IOPS vs throughput.
- disk queue depth.
- write amplification.
- compaction impact in LSM stores.

Database relevance:

- WAL fsync affects write latency.
- B-tree random I/O differs from LSM sequential write behavior.
- Checkpoints can create latency spikes.
- Disk saturation can look like database slowness.

## Networking Internals

Must know:

- TCP handshake.
- TLS handshake.
- DNS resolution.
- connection pooling.
- congestion control.
- retransmits.
- keepalive.
- MTU and fragmentation.
- NAT and ephemeral ports.
- load balancer idle timeout.

Common production failures:

- DNS outage or stale cache.
- TLS certificate expiry.
- ephemeral port exhaustion.
- connection pool starvation.
- packet loss causing tail latency.
- retries amplifying network congestion.

## TCP and HTTP Performance

Design points:

- Reuse connections.
- Prefer HTTP/2 or HTTP/3 where useful.
- Tune timeouts at each layer.
- Avoid tiny chatty calls.
- Use compression only when CPU trade-off is acceptable.
- Keep payloads bounded.
- Use CDN for static and media.

## Containers and Kubernetes Internals

Know:

- cgroups enforce CPU and memory limits.
- namespaces isolate process/network/filesystem views.
- container image layers affect startup and pull time.
- CPU limits can cause throttling.
- memory limit breach causes OOM kill.
- readiness probes remove pods from service endpoints.
- liveness probes restart unhealthy pods.
- preStop hooks and termination grace periods support draining.

Debugging signals:

- OOMKilled.
- CrashLoopBackOff.
- CPU throttling.
- high restart count.
- image pull backoff.
- DNS resolution failures.
- conntrack exhaustion.

## Infrastructure Debugging Playbook

For a latency spike:

1. Check user-facing SLO and affected routes.
2. Check deploy/config changes.
3. Check dependency latency.
4. Check CPU, memory, GC, thread pools.
5. Check DB query latency and lock waits.
6. Check network retransmits and DNS.
7. Check load balancer errors.
8. Check queue depth and back-pressure.
9. Check node-level saturation.
10. Mitigate before root-cause analysis if user impact is high.

## Interview Questions

1. What happens when a service runs out of file descriptors?
2. Why can CPU limits increase p99 latency in Kubernetes?
3. How do DNS failures show up in microservices?
4. How do TCP retransmits affect tail latency?
5. What is ephemeral port exhaustion?
6. How does page cache affect database performance?
7. How do you debug OOMKilled pods?
8. Why can an oversized thread pool reduce throughput?

