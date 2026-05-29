# Problem 133: Design a Global DNS System

## Problem Statement

Design a globally distributed DNS infrastructure similar to Route53 or Cloudflare DNS
that provides both authoritative nameserver and recursive resolver capabilities. The
system must deliver ultra-low latency DNS resolution worldwide, support advanced traffic
management policies, and withstand massive DDoS attacks while maintaining DNSSEC
integrity and supporting modern DNS protocols.

## Key Challenges

1. **Recursive Resolver with Caching**: Build a recursive resolver that efficiently
   resolves queries through the DNS hierarchy with intelligent caching, prefetching,
   and negative caching (NCACHE) to minimize upstream queries.
2. **Authoritative Nameserver**: Manage millions of DNS zones with support for all
   record types (A, AAAA, CNAME, MX, SRV, TXT, CAA, etc.) and instant propagation.
3. **Zone Management**: Provide APIs for zone CRUD operations, bulk record updates,
   and import/export with validation and conflict detection.
4. **DNSSEC**: Implement DNS Security Extensions with automated key generation,
   rotation (KSK/ZSK), and signing without operational burden on customers.
5. **Anycast Routing**: Deploy on a global anycast network so queries are automatically
   routed to the nearest point of presence via BGP.
6. **Health-Check Based Failover**: Integrate health checks with DNS responses to
   automatically remove unhealthy endpoints from resolution.
7. **Traffic Routing Policies**: Support weighted, latency-based, geolocation, and
   multi-value routing with configurable failover chains.
8. **DNS over HTTPS/TLS (DoH/DoT)**: Support encrypted DNS protocols for privacy
   while maintaining performance.
9. **DDoS Protection**: Withstand massive DNS amplification attacks and query floods
   while continuing to serve legitimate traffic.
10. **Zone Transfer (AXFR/IXFR)**: Support zone transfers for secondary nameservers
    with authentication and incremental updates.

## Scale Requirements

- Millions of hosted zones with billions of records
- 100M+ queries per second globally
- <5ms average response time from nearest PoP
- 100+ points of presence worldwide
- Withstand 1Tbps+ DDoS attacks
- Zone changes propagated globally in <60 seconds
- 100% uptime SLA for authoritative DNS

## Expected Discussion Areas

- DNS packet structure and wire format optimization
- Cache poisoning prevention (source port randomization, 0x20 encoding)
- Anycast vs unicast trade-offs for DNS
- TTL management and cache coherence
- DNSSEC chain of trust validation
- Query minimization (RFC 7816) for privacy
- DNS flag day compliance
