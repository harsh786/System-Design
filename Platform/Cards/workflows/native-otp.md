# Native OTP Workflow

## Overview

The Native OTP Processor handles inline OTP authentication for card payments, bypassing the traditional ACS redirect page. Instead of redirecting the customer to the issuer's 3DS authentication page, the system intercepts the OTP step and provides a native UI, improving conversion rates and user experience.

## Services Involved

| Service | Role |
|---------|------|
| Native OTP Processor | Core OTP orchestration (generate, submit, resend, cancel) |
| Card Gateway | Provides payment context via cache, receives routing callbacks |
| Redirect Listener | Fallback for non-native OTP scenarios |
| BIN Service | Identifies issuer for OTP config lookup |
| Card Gateway Cache (Redis) | Stores payment session data |
| Issuer ACS | Bank's authentication page (intercepted/automated) |

## Architecture

```mermaid
graph TB
    subgraph Client["Client Layer"]
        SDK[Payment SDK / Checkout]
    end

    subgraph NOP["Native OTP Processor"]
        Router[OTP Router]
        EligCheck[Eligibility Checker]
        ConfigHelper[Config Helper]
        
        subgraph Providers["OTP Providers"]
            Native[Native OTP Service]
            Juspay[Juspay DOTP Service]
            CGWRoute[CG Routing Helper]
        end
        
        subgraph IssuerImpl["Per-Issuer Implementations"]
            HDFC_OTP[HDFC Issuer Service]
            SBI_OTP[SBI Issuer Service]
            TestOTP[Test Issuer Service]
        end

        BrowserMgr[Browser Session Manager]
        PaymentStore[Payment Data Store]
    end

    subgraph External["External"]
        CGWCache[(Card Gateway Cache<br/>Redis)]
        ACS[Issuer ACS Page]
        CGW[Card Gateway]
    end

    SDK --> Router
    Router --> EligCheck
    EligCheck --> ConfigHelper
    ConfigHelper --> CGWCache
    
    Router --> Native
    Router --> Juspay
    Router --> CGWRoute
    
    Native --> IssuerImpl
    IssuerImpl --> BrowserMgr
    BrowserMgr --> ACS
    
    CGWRoute --> CGW
    PaymentStore --> CGWCache
```

## OTP Generation Sequence

```mermaid
sequenceDiagram
    participant SDK as Payment SDK
    participant NOP as Native OTP Processor
    participant Config as Config Helper
    participant Cache as CG Cache (Redis)
    participant ISF as Issuer Service Factory
    participant Browser as Browser Session
    participant ACS as Issuer ACS Page

    SDK->>NOP: POST /native/otp/generate {paymentId}
    
    NOP->>Cache: Read CG payment response
    Cache-->>NOP: Payment context (card BIN, acquirer, amount)
    
    NOP->>Config: Check OTP config for BIN/issuer
    
    alt Juspay DOTP Flow
        Config-->>NOP: routing_type = JUSPAY_DOTP
        NOP->>NOP: Return synthetic OTP page response
        NOP-->>SDK: OTP page ready (native UI)
    else Card Gateway Routing
        Config-->>NOP: routing_type = CARD_GATEWAY
        NOP->>NOP: Route via CardGatewayOtpRoutingHelper
        NOP-->>SDK: Redirect to CG flow
    else Native Flow
        Config-->>NOP: routing_type = NATIVE
        NOP->>ISF: Get issuer-specific service
        ISF-->>NOP: IssuerService (HDFC/SBI/etc.)
        
        NOP->>Browser: Create headless browser session
        Browser->>ACS: Navigate to ACS URL
        ACS-->>Browser: OTP page loaded
        
        Note over Browser: Parse page structure<br/>Extract OTP field info<br/>Detect OTP sent status
        
        Browser-->>NOP: Page ready, OTP sent by issuer
        NOP-->>SDK: OTP generation successful
    end
```

## OTP Submission Sequence

```mermaid
sequenceDiagram
    participant SDK as Payment SDK
    participant NOP as Native OTP Processor
    participant Cache as CG Cache
    participant ISF as Issuer Service
    participant Browser as Browser Session
    participant ACS as Issuer ACS Page
    participant RL as Redirect Listener
    participant CGW as Card Gateway

    SDK->>NOP: POST /native/otp/submit {paymentId, otp}
    
    NOP->>Cache: Read payment context
    Cache-->>NOP: Payment session data
    
    alt Juspay DOTP
        NOP->>NOP: JuspayNativeOtpService.submitOtp()
        Note over NOP: Submit to Juspay DOTP endpoint
    else Card Gateway Route
        NOP->>CGW: Forward OTP via CardGatewayOtpRoutingHelper
        CGW-->>NOP: Auth result
    else Native Flow
        NOP->>ISF: Get issuer service
        NOP->>Browser: Retrieve existing session
        Browser->>ACS: Enter OTP in field (CSS selector)
        Browser->>ACS: Click submit button
        
        Note over ACS: Validate OTP<br/>Generate authentication response
        
        ACS-->>Browser: Redirect with paRes/authResponse
        Browser-->>NOP: Authentication response captured
        
        NOP->>NOP: Extract authentication data (CAVV, ECI, status)
        NOP-->>SDK: OTP verification result
    end
```

## OTP Resend Sequence

```mermaid
sequenceDiagram
    participant SDK as Payment SDK
    participant NOP as Native OTP Processor
    participant Browser as Browser Session
    participant ACS as Issuer ACS Page

    SDK->>NOP: POST /native/otp/resend {paymentId}
    
    alt Juspay DOTP
        NOP->>NOP: JuspayNativeOtpService.resendOtp()
    else Native Flow
        NOP->>Browser: Get active session
        Browser->>ACS: Click resend link (CSS selector)
        ACS-->>Browser: New OTP sent confirmation
        Browser-->>NOP: Resend successful
    end
    
    NOP-->>SDK: OTP resent successfully
```

## Eligibility Check Flow

```mermaid
flowchart TD
    A[Payment Request] --> B[Extract BIN from card]
    B --> C{BIN-level config exists?}
    C -->|Yes| D{BIN config enabled?}
    D -->|Yes| E[Use BIN-level config]
    D -->|No| F[Check issuer-level config]
    C -->|No| F
    
    F --> G{Issuer config exists?}
    G -->|Yes| H{Issuer config enabled?}
    H -->|Yes| I[Use issuer-level config]
    H -->|No| J[Native OTP NOT eligible]
    G -->|No| J
    
    E --> K[Native OTP ELIGIBLE]
    I --> K
    
    K --> L{Routing Type?}
    L -->|NATIVE| M[Direct headless OTP]
    L -->|JUSPAY_DOTP| N[Juspay Dynamic OTP]
    L -->|CARD_GATEWAY| O[Route via Card Gateway]
    
    J --> P[Standard 3DS redirect flow]
```

## Activity Diagram - Full Native OTP Flow

```mermaid
flowchart TB
    subgraph Setup["Payment Setup"]
        S1[Customer initiates payment] --> S2[Card Gateway processes]
        S2 --> S3[3DS Enrollment with acquirer]
        S3 --> S4[ACS URL received]
        S4 --> S5[Cache payment context in Redis]
        S5 --> S6[Return to SDK: OTP required]
    end

    subgraph OTPFlow["Native OTP Flow"]
        O1[SDK calls /native/otp/generate] --> O2[Read CG cache]
        O2 --> O3[Resolve OTP config]
        O3 --> O4[Create browser session]
        O4 --> O5[Navigate to ACS URL]
        O5 --> O6[Wait for OTP page load]
        O6 --> O7[OTP sent to customer's phone]
        O7 --> O8[Return: ready for OTP input]
        
        O8 --> O9[Customer enters OTP in SDK]
        O9 --> O10[SDK calls /native/otp/submit]
        O10 --> O11[Enter OTP in browser session]
        O11 --> O12[Submit ACS form]
        O12 --> O13{Auth successful?}
        O13 -->|Yes| O14[Extract CAVV/ECI]
        O13 -->|No| O15{Retries remaining?}
        O15 -->|Yes| O16[Allow retry]
        O15 -->|No| O17[Authentication failed]
        O14 --> O18[Complete authorization]
    end

    subgraph Cleanup["Session Cleanup"]
        C1[Auth complete or timeout] --> C2[Close browser session]
        C2 --> C3[Clear payment store]
        C3 --> C4[Release resources]
    end
```

## Configuration Hierarchy

```
┌─────────────────────────────────────┐
│ BIN-Level Config (highest priority)  │
│ native_otp_bin_level_config          │
│ - Per BIN range                      │
│ - ACS page selectors                 │
│ - Payment routing config             │
├─────────────────────────────────────┤
│ Issuer-Level Config                  │
│ native_otp_config                    │
│ - Per issuer + network + card type   │
│ - OTP provider settings              │
│ - Feature toggles                    │
├─────────────────────────────────────┤
│ Global Defaults                      │
│ - Fallback to standard 3DS redirect  │
└─────────────────────────────────────┘
```

## Supported Issuers

| Issuer | Implementation | Notes |
|--------|---------------|-------|
| HDFC | `HdfcIssuerService` | Custom ACS page handling |
| SBI | `SbiIssuerService` | Custom ACS page handling |
| Test | `TestIssuerService` | For testing environments |
| Others | Juspay DOTP / CG Route | Via aggregator or fallback |

## Error Handling

| Error | Recovery |
|-------|----------|
| Browser session timeout | Return timeout error, allow retry |
| ACS page changed layout | Fall back to redirect, alert ops |
| OTP expired | Resend OTP (max 3 attempts) |
| OTP invalid (wrong code) | Allow retry within limit |
| Network error to ACS | Retry once, then fail |
| Config not found for BIN | Fall back to standard 3DS |

## Metrics & Monitoring

- OTP generation success rate per issuer
- OTP submission success rate per issuer
- Average OTP completion time
- Browser session failure rate
- Fallback-to-redirect rate
- Resend rate per issuer
