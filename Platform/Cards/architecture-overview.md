# Card Gateway Architecture Overview

## High-Level System Architecture

```mermaid
graph TB
    subgraph External["External Layer"]
        Merchant[Merchant/BFF]
        Networks[Card Networks<br/>Visa/MC/RuPay]
        Acquirers[Acquirer Banks<br/>HDFC/Axis/RBL/ICICI]
        Issuers[Issuer Banks]
    end

    subgraph Gateway["API Gateway"]
        Kong[Kong API Gateway]
        InternalGW[Internal Nginx Gateway]
    end

    subgraph Orchestration["Orchestration Layer"]
        OMS[Order Management Service]
        CGW[Card Gateway Service<br/>Plural_CardGatewayServicev21]
    end

    subgraph Processing["Processing Layer"]
        CCS[Card Connector Service]
        NGS[Network Gateway Service]
        NOP[Native OTP Processor]
        RL[Redirect Listener]
    end

    subgraph AcquirerConnectors["Acquirer Connectors"]
        HDFC[HDFC Connector]
        CYBS[Cybersource Connector]
        MPGS[MPGS Connector]
        RBL[RBL Connector]
        Fiserv[Fiserv Connector]
        Lyra[Lyra Connector]
        Wibmo[Wibmo Connector]
    end

    subgraph NetworkConnectors["Network Connectors"]
        VNC[Visa Network Connector]
        MNC[Mastercard Network Connector]
        RNC[RuPay Network Connector]
        WNC[Wibmo Network Connector]
    end

    subgraph DataServices["Data & Token Services"]
        CVS[Customer Vault Service]
        TMS[Token Management Service]
        AQS[Acquirer Service]
        BIN[Global BIN Service]
        TBM[Token BIN Mapping Service]
    end

    subgraph Storage["Storage Layer"]
        PG_CGW[(PostgreSQL<br/>Card Gateway DB)]
        PG_CV[(PostgreSQL<br/>Customer Vault DB)]
        PG_TM[(PostgreSQL<br/>Token Mgm DB)]
        PG_NOP[(PostgreSQL<br/>Native OTP DB)]
        Redis[(Redis Cache)]
        Kafka[Apache Kafka<br/>MSK]
    end

    Merchant --> Kong --> OMS
    OMS --> CGW
    CGW --> CCS
    CGW --> NGS
    CGW --> NOP
    CGW --> AQS
    CGW --> BIN
    CGW --> CVS

    CCS --> HDFC & CYBS & MPGS & RBL & Fiserv & Lyra & Wibmo
    NGS --> VNC & MNC & RNC & WNC

    HDFC & CYBS & MPGS & RBL --> Acquirers
    VNC & MNC & RNC --> Networks

    CVS --> TMS
    TMS --> NGS

    RL --> OMS
    RL --> CGW
    Networks --> RL
    Acquirers --> RL

    CGW --> PG_CGW
    CVS --> PG_CV
    TMS --> PG_TM
    NOP --> PG_NOP
    CGW --> Redis
    NOP --> Redis
    CGW --> Kafka
```

## Service Communication Patterns

```mermaid
graph LR
    subgraph Synchronous["Sync (HTTP/REST)"]
        direction TB
        S1[CGW -> Acquirer Service]
        S2[CGW -> BIN Service]
        S3[CGW -> Card Connector -> Acquirer]
        S4[CGW -> Network Gateway -> Network Connector]
        S5[CVS -> Token Mgm Service]
        S6[NOP -> Card Gateway Cache]
    end

    subgraph Async["Async (Kafka)"]
        direction TB
        A1[CGW -> Transaction Events]
        A2[CVS -> Outbox Events]
        A3[Token Lifecycle Events]
        A4[Payment Status Events]
    end

    subgraph Callbacks["Callbacks (HTTP POST)"]
        direction TB
        C1[Acquirer 3DS -> Redirect Listener]
        C2[Visa Passkey -> Redirect Listener]
        C3[MC Passkey -> Redirect Listener]
        C4[Network Webhooks -> Token Mgm Service]
    end
```

## Technology Stack

| Layer | Technology | Details |
|-------|-----------|---------|
| **Orchestration** | Java 11, Spring Boot 2.7, WebFlux | Card Gateway, Redirect Listener, Acquirer Service |
| **NXT Services** | Kotlin 1.9+, Ktor 2.3 | Network Gateway, Customer Vault, Token Mgm, Native OTP |
| **Network Connectors** | Java, Spring Boot WebFlux | Visa, Mastercard, RuPay |
| **Acquirer Connectors** | Java, Spring Boot WebFlux | HDFC, MPGS, Cybersource, RBL, Fiserv |
| **Database** | PostgreSQL (Aurora RDS) | Primary data store (migrating from MSSQL) |
| **Cache** | Redis (ElastiCache) | Payment session, acquirer config, BIN data |
| **Messaging** | Apache Kafka (AWS MSK) | Event streaming with IAM auth |
| **Discovery** | Kubernetes DNS + Nginx Ingress | Internal service mesh |
| **Config** | Spring Cloud Config Server | Git-backed config per environment |
| **Observability** | OpenTelemetry, Prometheus, Loki, Grafana | Traces, metrics, logs |

## Data Flow - Card Payment Lifecycle

```mermaid
stateDiagram-v2
    [*] --> PaymentInitiated: Merchant creates order
    PaymentInitiated --> BINResolved: BIN lookup
    BINResolved --> AcquirerSelected: Route to acquirer
    AcquirerSelected --> TokenResolved: Check COFT/Network Token

    TokenResolved --> Enrolled: 3DS Enrollment
    TokenResolved --> CryptogramGenerated: COFT with cryptogram

    CryptogramGenerated --> Enrolled: Enrollment with token

    Enrolled --> AuthenticationPending: Redirect to ACS
    Enrolled --> Authorized: Frictionless (ECI 05)

    AuthenticationPending --> Authenticated: OTP/Passkey/Biometric
    AuthenticationPending --> Failed: Auth timeout/failure

    Authenticated --> Authorized: Authorization with CAVV
    Authorized --> Captured: Capture
    Authorized --> Voided: Void

    Captured --> Refunded: Refund
    Captured --> Settled: Settlement

    Failed --> [*]
    Voided --> [*]
    Refunded --> [*]
    Settled --> [*]
```

## Service Responsibilities Matrix

| Responsibility | Service | Notes |
|---------------|---------|-------|
| Payment orchestration | Card Gateway | Process, Auth, Capture, Refund, Void, Inquiry |
| Acquirer routing | Card Gateway + Acquirer Service | Based on merchant config, BIN, network |
| Connector dispatch | Card Connector Service | Routes to per-acquirer connector |
| 3DS enrollment | Acquirer Connectors | Via acquirer's 3DS server |
| Network token provisioning | Network Gateway Service | TRID, Enroll, Cryptogram, Delete |
| Token storage | Token Management Service | CRUD, lifecycle, cryptogram delegation |
| Customer management | Customer Vault Service | Profiles, saved cards, OTP |
| BIN resolution | Global BIN Service | Card type, issuer, network, country |
| Token-BIN mapping | Token BIN Mapping Service | Network token to PAN BIN resolution |
| Native OTP | Native OTP Processor | ACS page bypass for select issuers |
| Async callbacks | Redirect Listener | 3DS, passkey, wallet callbacks |
| Passkey auth | Network Gateway + VNC | Visa VPP, MC SRC passkey |

## Environment Architecture

```mermaid
graph TB
    subgraph Production["Production (EKS)"]
        ProdPrimary[ap-south-1<br/>Primary]
        ProdDR[DR Region<br/>Disaster Recovery]
    end

    subgraph NonProd["Non-Production"]
        Dev[Dev Cluster]
        UAT[UAT Cluster]
    end

    subgraph Shared["Shared Infrastructure"]
        MSK[AWS MSK<br/>Kafka]
        RDS[Aurora PostgreSQL<br/>Multi-AZ]
        EC[ElastiCache Redis<br/>Cluster Mode]
        SM[AWS Secrets Manager]
        ECR[ECR Container Registry]
    end

    ProdPrimary --> MSK & RDS & EC
    ProdDR --> MSK & RDS & EC
    Dev --> MSK & RDS & EC
```

## Key Integration Points

### External Network APIs
- **Visa**: VTS (Visa Token Service) for CoFT, VPP (Visa Payment Passkey) for authentication
- **Mastercard**: MDES (Mastercard Digital Enablement Service), SRC (Secure Remote Commerce)
- **RuPay/NPCI**: TokenHub for CoFT, via direct API or Wibmo/HDFC-FSS proxy

### Internal Service Dependencies
```
Card Gateway depends on:
  ├── Acquirer Service (merchant-acquirer config)
  ├── Global BIN Service (card metadata)
  ├── Card Connector Service (acquirer dispatch)
  ├── Network Gateway Service (tokenization + passkey)
  ├── Customer Vault Service (saved cards lookup)
  ├── Native OTP Processor (native auth)
  ├── Redirect Listener (async callback receiver)
  ├── Token BIN Mapping Service (token BIN resolution)
  └── OMS (order lifecycle management)
```
