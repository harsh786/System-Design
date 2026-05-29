# Problem 122: Design a Chaos Engineering Platform

## Problem Statement

Design a Chaos Engineering Platform similar to Gremlin, LitmusChaos, or Netflix's Chaos Monkey/ChAP. The platform should enable teams to proactively discover weaknesses in distributed systems by injecting controlled failures in production and pre-production environments.

## Key Challenges

### 1. Fault Injection Mechanisms
- Network faults: latency injection, packet loss, DNS failures, partition simulation
- Resource stress: CPU saturation, memory pressure, disk fill, IO throttling
- Process-level: process kill, service crash, dependency unavailability
- Platform-level: pod eviction, node drain, AZ failure simulation

### 2. Blast Radius Control
- Progressive expansion (start small, grow if safe)
- Targeting specific services, pods, or percentage of traffic
- Geographic and temporal scoping
- Preventing cascading failures beyond experiment scope

### 3. Steady-State Hypothesis
- Defining expected system behavior before experiment
- Automated validation of hypothesis during/after injection
- SLO-based abort conditions

### 4. Automated Game Days
- Scheduling recurring chaos experiments
- Playbook-based experiment sequences
- Cross-team coordination for large-scale game days

### 5. Safety Mechanisms
- Automatic abort on SLO breach
- Manual kill switch accessible to all operators
- Pre-flight safety checks before injection
- Rollback verification

### 6. Compliance & Approval Workflow
- Change management integration
- Risk assessment scoring
- Approval gates for production experiments
- Audit trail for all chaos activities

## Scale Requirements
- 10K+ microservices eligible for chaos
- Safe for production environments
- Support for Kubernetes, VMs, serverless
- Integration with existing observability stack
- Sub-second abort response time

## Expected Design Areas
- Chaos controller architecture
- Fault injection agent design
- Safety and abort system
- Experiment lifecycle management
- Observability integration
- Approval and compliance workflow
