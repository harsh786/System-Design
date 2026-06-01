# BIN Service Workflow

## Overview

The BIN (Bank Identification Number) Service provides card metadata resolution from the first 6-8 digits of a card number. It identifies the card network, issuer, card type, and capabilities. Multiple BIN services exist for different use cases: global BIN lookup, token-to-BIN mapping, and batch BIN data loading.

## Services Involved

| Service | Tech | Role |
|---------|------|------|
| `Plural_GlobalBINServicev21` | Java, Spring Boot WebFlux | Primary BIN metadata API |
| `Plural_Repo_GlobalBinService` | Node.js/TypeScript, Express | Legacy BFF proxy to .NET service |
| `Plural_TokenBinMapping_Service` | Java, Spring Boot | Token BIN to PAN BIN resolution |
| `Plural_BatchLoadBinData_Service` | Java | Bulk BIN data loading from networks |

## Architecture

```mermaid
graph TB
    subgraph Consumers["Consumers"]
        CGW[Card Gateway]
        OMS[Order Management]
        PayOpt[Payment Options Service]
    end

    subgraph BINServices["BIN Services"]
        GlobalBIN[Global BIN Service v21<br/>POST /v3/bin/metadata]
        LegacyBIN[Global BIN Service BFF<br/>POST /api/v1/globalbin/GetBinData]
        TokenBIN[Token BIN Mapping<br/>POST /v1/binmapping/token]
        BatchLoad[Batch Load BIN Data]
    end

    subgraph Storage["Storage"]
        BINDB[(BIN Database<br/>GLOBAL_BIN_TBL)]
        TokenBINDB[(Token BIN Mapping DB)]
        Files[Network BIN Files<br/>Visa/MC/RuPay]
    end

    CGW --> GlobalBIN
    CGW --> TokenBIN
    OMS --> GlobalBIN
    PayOpt --> GlobalBIN
    
    GlobalBIN --> BINDB
    LegacyBIN --> BINDB
    TokenBIN --> TokenBINDB
    BatchLoad --> BINDB
    BatchLoad --> Files
```

## BIN Lookup Sequence

```mermaid
sequenceDiagram
    participant CGW as Card Gateway
    participant BIN as Global BIN Service v21
    participant DB as BIN Database
    participant Cache as Redis Cache

    CGW->>BIN: POST /v3/bin/metadata {bin: "411111"}
    
    BIN->>Cache: Check BIN cache
    
    alt Cache hit
        Cache-->>BIN: Cached BIN data
    else Cache miss
        BIN->>DB: SELECT FROM GLOBAL_BIN_TBL WHERE BIN_NUMBER = ?
        DB-->>BIN: BIN record
        BIN->>Cache: Cache result (TTL: 24h)
    end

    BIN-->>CGW: GlobalBinResponse
    Note over CGW: Response includes:<br/>card_scheme, card_type,<br/>issuer_name, issuer_id,<br/>country_code, is_regulated,<br/>emi_eligible, token_pan_bin
```

## Token BIN Resolution Sequence

```mermaid
sequenceDiagram
    participant CGW as Card Gateway
    participant TBM as Token BIN Mapping Service
    participant DB as Token BIN DB

    Note over CGW: Transaction with network token<br/>Need to know original card BIN

    CGW->>TBM: POST /v1/binmapping/token {network_token_bin: "489537"}
    
    TBM->>DB: Lookup token BIN range
    DB-->>TBM: Mapped PAN BIN data
    
    TBM-->>CGW: {original_bin, card_scheme, issuer, card_type}

    Note over CGW: Now can apply routing rules<br/>based on original card attributes
```

## BIN Data Loading Flow

```mermaid
sequenceDiagram
    participant Admin as Operations/Admin
    participant TBM as Token BIN Mapping Service
    participant Files as Network BIN Files
    participant DB as Token BIN DB

    Admin->>TBM: POST /v1/binmapping/load {network_type: "VISA", file_path}
    
    TBM->>Files: Read network BIN range file
    Files-->>TBM: BIN range data (CSV/proprietary format)
    
    Note over TBM: Parse network-specific format<br/>Visa, Mastercard, or RuPay

    loop For each BIN range
        TBM->>DB: UPSERT BIN mapping record
    end

    TBM-->>Admin: Load complete ({count} records processed)

    Admin->>TBM: POST /v1/binmapping/filestatus
    TBM-->>Admin: Last load status per network
```

## Activity Diagram - BIN Resolution in Payment Flow

```mermaid
flowchart TD
    A[Payment initiated with card number] --> B[Extract first 6-8 digits as BIN]
    B --> C[Call Global BIN Service]
    C --> D{BIN found?}
    D -->|No| E[Return error: Unsupported card]
    D -->|Yes| F[Get card metadata]
    
    F --> G[Card Network identified]
    F --> H[Card Type identified]
    F --> I[Issuer identified]
    
    G --> J{Network supported?}
    J -->|No| E
    J -->|Yes| K[Route to acquirer]
    
    H --> L{Card type eligible?}
    L -->|No| M[Return: Card type not supported]
    L -->|Yes| K
    
    I --> N{Issuer config available?}
    N --> O[Check EMI eligibility]
    N --> P[Check Native OTP support]
    N --> Q[Check tokenization support]
    
    K --> R[Select acquirer based on:<br/>- Network type<br/>- Card type<br/>- Merchant config<br/>- BIN attributes]
    
    subgraph TokenBIN["Token BIN Resolution"]
        T1[Transaction uses network token] --> T2[Extract token BIN prefix]
        T2 --> T3[Call Token BIN Mapping Service]
        T3 --> T4[Resolve to original PAN BIN]
        T4 --> T5[Apply same routing logic<br/>as regular BIN]
    end
```

## BIN Data Structure

```mermaid
erDiagram
    GLOBAL_BIN_TBL {
        bigint ID PK
        varchar BIN_NUMBER "6-8 digit BIN"
        varchar CARD_SCHEME "VISA/MASTERCARD/RUPAY/AMEX/DINERS"
        varchar CARD_TYPE "CREDIT/DEBIT/PREPAID"
        varchar CARD_ISSUER "Bank name"
        varchar ISSUER_ID "Internal issuer code"
        varchar COUNTRY_CODE "IN/US/GB etc"
        varchar TOKEN_PAN_BIN "Network token BIN range"
        bit IS_REGULATED "Regulated BIN flag"
        int BIN_LENGTH "6 or 8"
        varchar CARD_CATEGORY "CONSUMER/CORPORATE/COMMERCIAL"
        bit IS_INTERNATIONAL "International card flag"
        bit EMI_ELIGIBLE "EMI support flag"
    }

    TOKEN_BIN_MAPPING {
        bigint ID PK
        varchar TOKEN_BIN_START "Token BIN range start"
        varchar TOKEN_BIN_END "Token BIN range end"
        varchar NETWORK_TYPE "VISA/MASTERCARD/RUPAY"
        varchar ORIGINAL_BIN "Corresponding PAN BIN"
        varchar ISSUER_NAME
        varchar CARD_TYPE
        timestamp LOADED_AT
        varchar FILE_REFERENCE "Source file"
    }
```

## Use Cases for BIN Lookup

| Use Case | Consumer Service | What it determines |
|----------|-----------------|-------------------|
| Payment routing | Card Gateway | Which acquirer to use |
| Card validation | Payment Options | Is card type supported |
| EMI eligibility | EMI Service | Can EMI be offered |
| Native OTP | Native OTP Processor | Is native OTP available for this issuer |
| Tokenization | Token Mgm Service | Which network connector to use |
| International detection | Card Gateway | Is card international (different MDR) |
| Regulatory check | Compliance | Is BIN regulated (affects interchange) |

## API Reference

### Global BIN Service v21

```
POST /v3/bin/metadata
Request:
{
  "bins": ["411111", "524301", "607123"],
  "merchant_id": "M123" (optional)
}

Response:
{
  "data": [
    {
      "bin": "411111",
      "card_scheme": "VISA",
      "card_type": "CREDIT",
      "card_issuer": "HDFC Bank",
      "issuer_id": "HDFC",
      "country_code": "IN",
      "is_regulated": false,
      "emi_eligible": true,
      "token_pan_bin": "489537",
      "card_category": "CONSUMER"
    }
  ]
}
```

### Token BIN Mapping Service

```
POST /v1/binmapping/token
Request:
{
  "token_bin": "489537"
}

Response:
{
  "original_bin": "411111",
  "network_type": "VISA",
  "card_type": "CREDIT",
  "issuer": "HDFC Bank"
}

---

GET /v1/binmapping/bin/{BIN}
Response:
{
  "bin": "411111",
  "network_type": "VISA"
}

---

POST /v1/binmapping/load
Request:
{
  "network_type": "VISA",
  "file_path": "/data/visa-bin-ranges-2024.csv"
}
```

## Data Sources

| Network | BIN File Format | Update Frequency |
|---------|----------------|-----------------|
| Visa | VTS BIN Range file (CSV) | Monthly |
| Mastercard | MDES BIN Range file | Monthly |
| RuPay | NPCI BIN file | Quarterly |
| Global BIN | Network consortium + internal | Weekly updates |
