# Network Services (Visa, Mastercard, RuPay)

## Overview

The Network Services layer handles direct communication with card networks for tokenization (CoFT), Payment Account Reference (PAR) lookups, merchant onboarding (TRID), and authentication (Passkey). Each network has a dedicated connector service, orchestrated by the Network Gateway Service.

## Architecture

```mermaid
graph TB
    subgraph Gateway["Network Gateway Service (Kotlin/Ktor)"]
        Router[Network Router]
        Factory[NetworkConnectorFactory]
        MerchAdapter[Merchant Service Adapter]
    end

    subgraph Connectors["Network Connectors (Java/Spring WebFlux)"]
        VNC[Visa Network Connector<br/>VTS + VPP + PAR]
        MNC[Mastercard Network Connector<br/>MDES + SRC + PAR]
        RNC[RuPay Network Connector<br/>NPCI TokenHub]
        WNC[Wibmo Network Connector<br/>RuPay via HDFC-FSS]
    end

    subgraph Networks["Card Networks"]
        Visa[Visa<br/>VTS API / VPP API]
        MC[Mastercard<br/>MDES API / SRC API]
        NPCI[NPCI/RuPay<br/>TokenHub API]
        Wibmo[Wibmo/HDFC-FSS<br/>Proxy API]
    end

    Router --> Factory
    Factory -->|VISA| VNC
    Factory -->|MASTERCARD| MNC
    Factory -->|RUPAY| RNC
    Factory -->|RPD/HDFC-FSS| WNC

    VNC --> Visa
    MNC --> MC
    RNC --> NPCI
    WNC --> Wibmo
```

## Network Routing Decision

```mermaid
flowchart TD
    A[Request from Card Gateway/Token Service] --> B[Network Gateway Service]
    B --> C{Network Type from BIN}
    C -->|VISA| D[VisaConnector]
    C -->|MASTERCARD| E[MasterCardConnector]
    C -->|RUPAY| F{isRoutingViaWibmoForRupayHdfcFss?}
    F -->|Yes| G[WibmoConnector]
    F -->|No| H[RupayConnector]
    
    D --> I[Visa VTS/VPP APIs]
    E --> J[MC MDES/SRC APIs]
    G --> K[Wibmo Proxy to NPCI]
    H --> L[Direct NPCI TokenHub]
```

---

## Visa Network Connector

### Operations

| Operation | Controller | Endpoint | Description |
|-----------|-----------|----------|-------------|
| Token Provisioning | `CybsNetworkTokenController` | POST `/v1/network/provisionNetworkToken` | Provision DPAN via VTS |
| Cryptogram | `CybsNetworkTokenController` | POST `/v1/network/generateCryptogram/{instrumentId}` | Generate TAVV |
| Token Deletion | `CybsNetworkTokenController` | DELETE `/v1/network/deleteToken/{instrumentId}` | Delete network token |
| Card Encryption | `CybsNetworkTokenController` | GET `/v1/network/encryptCard` | Encrypt card for VTS |
| PAR Lookup | `VisaNetworkConnectorController` | POST `/v1/network/par` | Get Payment Account Reference |
| Guest Checkout | `VisaNetworkConnectorController` | POST `/v1/network/alt-token` | ALT token for guest |
| Passkey Eligibility | `VisaPasskeyController` | POST `/v1/network/passkey/eligibility` | Check VPP eligibility |
| Passkey Lookup | `VisaPasskeyController` | POST `/v1/network/passkey/lookup` | Lookup auth methods |
| Passkey Binding | `VisaPasskeyController` | POST `/v1/network/passkey/binding` | Bind new passkey |

### Visa Token Provisioning Sequence

```mermaid
sequenceDiagram
    participant NGS as Network Gateway
    participant VNC as Visa Connector
    participant VTS as Visa Token Service

    NGS->>VNC: POST /v1/network/provisionNetworkToken
    Note over VNC: Request: encrypted_card_data,<br/>TRID, merchant_name

    VNC->>VNC: Build VTS request payload
    VNC->>VNC: JWE encrypt card data with Visa public key
    VNC->>VTS: POST /vts/provisioning/provision
    
    Note over VTS: Validate TRID<br/>Decrypt card data<br/>Check with issuer<br/>Provision DPAN

    VTS-->>VNC: Response (DPAN, expiry, PAR, token_ref_id, status)
    VNC->>VNC: Map to internal response format
    VNC-->>NGS: {network_token, expiry, par, reference_id, status}
```

### Visa Cryptogram Generation

```mermaid
sequenceDiagram
    participant NGS as Network Gateway
    participant VNC as Visa Connector
    participant VTS as Visa Token Service

    NGS->>VNC: POST /v1/network/generateCryptogram/{instrumentId}
    Note over VNC: instrumentId = VTS token reference

    VNC->>VTS: POST /vts/cryptogram/generate
    Note over VTS: Generate TAVV<br/>(Token Authentication<br/>Verification Value)

    VTS-->>VNC: {cryptogram (TAVV), eci, type}
    VNC-->>NGS: Cryptogram response
```

---

## Mastercard Network Connector

### Operations

| Operation | Description |
|-----------|-------------|
| Merchant Onboarding | TRID registration with MC MDES |
| Guest Checkout (ALT Token) | Token for non-enrolled transactions |
| PAR Lookup | Payment Account Reference retrieval |
| Token Provisioning | DPAN provisioning via MDES |
| Cryptogram | DTVV generation |

### Mastercard Token Provisioning Sequence

```mermaid
sequenceDiagram
    participant NGS as Network Gateway
    participant MNC as MC Connector
    participant MDES as MC Digital Enablement

    NGS->>MNC: POST /v1/network/provision
    Note over MNC: Request: card_data,<br/>TRID, merchant_info

    MNC->>MNC: Encrypt card with MC public key
    MNC->>MDES: POST /digitization/digitize
    
    Note over MDES: Validate Token Requestor<br/>Verify with Issuer<br/>Assign DPAN + PAR

    MDES-->>MNC: {tokenUniqueReference, DPAN, expiry, PAR, status}
    MNC->>MNC: Map response
    MNC-->>NGS: Provisioning result
```

### Mastercard Merchant Onboarding

```mermaid
sequenceDiagram
    participant NGS as Network Gateway
    participant MNC as MC Connector
    participant MDES as Mastercard

    NGS->>MNC: POST /v1/network/onboard
    Note over MNC: Merchant onboarding request<br/>merchant_name, MCC, TRID

    MNC->>MNC: Build onboarding payload
    MNC->>MDES: POST /merchant/onboarding
    
    Note over MDES: Register Token Requestor<br/>Assign TRID<br/>Configure permissions

    MDES-->>MNC: {trid, status, reference}
    MNC-->>NGS: Onboarding result
```

---

## RuPay Network Connector

### Operations

| Operation | Service | Description |
|-----------|---------|-------------|
| CoFT Provisioning | `RupayCoftService` | Network token via NPCI TokenHub |
| Cryptogram | `RupayCoftService` | TAV generation |
| Token Deletion | `RupayCoftService` | Remove token from TokenHub |
| PAR Lookup | `RupayCoftService` | Payment Account Reference |
| Webhook Update | `RupayCoftService` | Token lifecycle from NPCI |
| Guest Checkout | `RupayClientService` | ALT token for guest |

### RuPay Token Provisioning Sequence

```mermaid
sequenceDiagram
    participant NGS as Network Gateway
    participant RNC as RuPay Connector
    participant TokenHub as NPCI TokenHub

    NGS->>RNC: POST /v1/network/coft/provision
    Note over RNC: Request: card_data,<br/>TRID, merchant_info

    RNC->>RNC: Encrypt card data
    RNC->>TokenHub: POST /token/provision
    
    Note over TokenHub: Validate TRID<br/>Check with Issuer<br/>Provision RuPay Token<br/>Assign PAR

    TokenHub-->>RNC: {token, expiry, PAR, reference, status}
    RNC->>RNC: Map to internal format
    RNC-->>NGS: Provisioning result
```

### RuPay via Wibmo (HDFC-FSS)

```mermaid
sequenceDiagram
    participant NGS as Network Gateway
    participant WNC as Wibmo Connector
    participant Wibmo as Wibmo/HDFC-FSS
    participant NPCI as NPCI TokenHub

    NGS->>WNC: POST /v1/network/provision (RPD network)
    Note over WNC: RuPay via HDFC-FSS Wibmo proxy

    WNC->>Wibmo: Provision request
    Wibmo->>NPCI: Forward to TokenHub
    NPCI-->>Wibmo: Token provisioned
    Wibmo-->>WNC: Token response
    WNC-->>NGS: Provisioning result
```

---

## Cross-Network Comparison

### Token Provisioning

```mermaid
flowchart LR
    subgraph Visa["Visa Flow"]
        V1[JWE Encrypt Card] --> V2[VTS Provisioning API]
        V2 --> V3[DPAN + TAVV capability]
    end

    subgraph MC["Mastercard Flow"]
        M1[MC Key Encrypt] --> M2[MDES Digitize API]
        M2 --> M3[DPAN + DTVV capability]
    end

    subgraph RuPay["RuPay Flow"]
        R1[Encrypt Card] --> R2[NPCI TokenHub API]
        R2 --> R3[Token + TAV capability]
    end
```

### Cryptogram Types

| Network | Cryptogram | Name | Use |
|---------|-----------|------|-----|
| Visa | TAVV | Token Authentication Verification Value | Per-transaction auth proof |
| Mastercard | DTVV | Dynamic Token Verification Value | Per-transaction auth proof |
| RuPay | TAV | Token Authentication Value | Per-transaction auth proof |

### PAR (Payment Account Reference)

```mermaid
flowchart TD
    A[Same physical card] --> B[PAR: unique per-card identifier]
    B --> C[Visa DPAN 1 - Merchant A]
    B --> D[Visa DPAN 2 - Merchant B]
    B --> E[MC DPAN 3 - Merchant C]
    
    Note over B: PAR stays same across<br/>all tokens for same card
```

## Security & Authentication

| Network | Auth Method | Encryption |
|---------|------------|------------|
| Visa | Mutual TLS + API Key | JWE (RSA-OAEP, A256GCM) |
| Mastercard | Mutual TLS + OAuth 2.0 | JWE (network-specific) |
| RuPay/NPCI | Mutual TLS + Digital Signature | Network encryption |
| Wibmo | API Key + TLS | Standard TLS |

## Error Handling by Network

| Scenario | Visa | Mastercard | RuPay |
|----------|------|-----------|-------|
| Token provisioning failed | VTS error code mapping | MDES error mapping | TokenHub error codes |
| Cryptogram timeout | Retry (max 2) | Retry (max 2) | Retry (max 2) |
| Network unreachable | Circuit breaker, alert | Circuit breaker, alert | Circuit breaker, alert |
| Invalid TRID | Re-register TRID | Re-register TRID | Re-register TRID |
| Card not eligible | Return ineligible to caller | Return ineligible | Return ineligible |

## Configuration

Each network connector requires:
- **Certificates**: Mutual TLS certs per environment (sandbox/prod)
- **API Credentials**: API keys, OAuth client credentials
- **TRID**: Pre-registered Token Requestor ID
- **Encryption Keys**: Network public keys for card encryption (rotated periodically)
- **Webhook URLs**: Registered with networks for token lifecycle callbacks
