# Passkey Workflow (Visa Payment Passkey / Mastercard SRC)

## Overview

The Passkey workflow enables FIDO2/WebAuthn-based biometric authentication for card payments, replacing traditional OTP-based 3DS authentication. Plural supports Visa Payment Passkey (VPP) and Mastercard SRC Passkey, providing a frictionless checkout experience using device biometrics (fingerprint, face recognition).

## Services Involved

| Service | Role |
|---------|------|
| Card Gateway | Orchestrates passkey flow, extended landing page, status mapping |
| Network Gateway Service | Passkey eligibility, lookup, binding API delegation |
| Visa Network Connector | VPP APIs (eligibility, lookup, binding) |
| Mastercard Network Connector | MC SRC passkey APIs |
| Redirect Listener | Handles passkey auth callbacks from Visa/MC |
| OMS | Order lifecycle + authorization trigger |

## Two Passkey Flows

```mermaid
flowchart TD
    A[Payment initiated] --> B[Card Gateway /process]
    B --> C[Check passkey eligibility]
    C --> D[Passkey lookup via Network Gateway]
    D --> E{Passkey status?}
    
    E -->|ACTIVE| F[Authentication Flow<br/>User has existing passkey]
    E -->|NOT_FOUND| G[Binding Flow<br/>User needs to create passkey]
    E -->|ERROR| H[Fall back to standard 3DS]
    
    F --> I[Biometric authentication]
    I --> J[Authorization with auth code]
    
    G --> K[Standard 3DS authentication first]
    K --> L[After successful auth, offer passkey binding]
    L --> M[User creates passkey or skips]
```

---

## Authentication Flow (Passkey Exists)

```mermaid
sequenceDiagram
    participant Browser as Customer Browser
    participant OMS as Order Management
    participant CGW as Card Gateway
    participant NGS as Network Gateway
    participant VNC as Visa Network Connector
    participant Visa as Visa VPP
    participant RL as Redirect Listener
    participant CCS as Card Connector
    participant ACQ as Acquirer (CYBS)

    Browser->>OMS: Initiate payment (saved card)
    OMS->>CGW: POST /process (payment request)
    
    Note over CGW: Extended landing page mode<br/>Includes Visa SDK init script

    CGW-->>Browser: Landing page HTML + Visa SDK JS

    Browser->>Browser: Load Visa SDK, collect device data
    Browser->>RL: POST /enroll (browser + SDK data)
    RL->>CGW: POST /authenticate (forwarded)

    CGW->>NGS: POST /api/v1/network/authenticate/look-up/methods
    NGS->>VNC: POST /v1/network/passkey/lookup
    VNC->>Visa: Passkey lookup (prompt=login)
    
    Note over Visa: Check if PAR has<br/>registered passkey

    Visa-->>VNC: Status: ACTIVE (passkey found)
    VNC-->>NGS: Passkey active
    NGS-->>CGW: ACTIVE status

    Note over CGW: Return auth redirect HTML<br/>to invoke Visa biometric

    CGW-->>Browser: Redirect to Visa auth page

    Browser->>Visa: Biometric authentication (FIDO2)
    
    Note over Visa: User authenticates with<br/>fingerprint/face/PIN

    Visa->>RL: POST /visa/responsehandler/{acquirer} (authCode)
    
    RL->>RL: Extract authCode from callback
    RL->>OMS: Trigger authorization
    OMS->>CGW: POST /authorize

    CGW->>CCS: Enroll with authCode (frictionless)
    CCS->>ACQ: CYBS enrollment + authCode
    ACQ-->>CCS: ECI=05, CAVV (frictionless auth)
    CCS-->>CGW: Authentication successful

    CGW->>CCS: Authorize payment
    CCS->>ACQ: Authorization request
    ACQ-->>CCS: AUTHORIZED
    CCS-->>CGW: Auth response
    CGW-->>OMS: Payment authorized
    OMS-->>Browser: Redirect to merchant success URL
```

## Binding Flow (Passkey Not Found)

```mermaid
sequenceDiagram
    participant Browser as Customer Browser
    participant OMS as Order Management
    participant CGW as Card Gateway
    participant NGS as Network Gateway
    participant VNC as Visa Network Connector
    participant Visa as Visa VPP
    participant RL as Redirect Listener
    participant CCS as Card Connector
    participant ACQ as Acquirer

    Browser->>OMS: Initiate payment
    OMS->>CGW: POST /process
    CGW-->>Browser: Extended landing page

    Browser->>RL: POST /enroll (browser data)
    RL->>CGW: POST /authenticate

    CGW->>NGS: POST /api/v1/network/authenticate/look-up/methods
    NGS->>VNC: Passkey lookup
    VNC->>Visa: Lookup (prompt=login)
    Visa-->>VNC: Status: NOT_FOUND
    VNC-->>NGS: Not found
    NGS-->>CGW: NOT_FOUND

    Note over CGW: PASSKEY_BINDING_REQUIRED<br/>Proceed with normal 3DS first

    CGW->>CCS: Standard 3DS enrollment
    CCS->>ACQ: Enrollment request
    ACQ-->>CCS: ACS URL + challenge required
    CCS-->>CGW: Enrollment response

    CGW-->>Browser: Redirect to ACS (OTP challenge)
    Browser->>ACQ: Complete 3DS challenge (OTP)
    ACQ->>RL: 3DS callback (paRes)
    
    RL->>OMS: Authorization request
    OMS->>CGW: POST /authorize
    CGW->>CCS: Authorize with CAVV
    CCS->>ACQ: Authorization
    ACQ-->>CCS: AUTHORIZED
    CCS-->>CGW: Success
    CGW-->>OMS: Authorized

    Note over RL: Payment successful!<br/>Now initiate passkey binding

    RL->>CGW: POST /passkey/binding (acsTxnId)
    CGW->>NGS: POST /api/v1/network/passkey/binding
    NGS->>VNC: POST /v1/network/passkey/binding
    VNC->>Visa: Initiate binding (prompt=create)
    Visa-->>VNC: Binding redirect URL
    VNC-->>NGS: Binding page HTML
    NGS-->>CGW: Binding response
    CGW-->>RL: Binding HTML

    RL-->>Browser: Show Visa binding UI + merchant redirect
    
    Note over Browser: User sees Visa passkey<br/>registration prompt<br/>(can skip or create)

    Browser->>Visa: Create passkey (or skip)
    Visa->>RL: POST /passkey/binding/callback/{acquirer}
    
    Note over RL: Non-blocking!<br/>Payment already succeeded

    RL-->>Browser: Redirect to merchant (payment done)
```

## Passkey Eligibility Check

```mermaid
flowchart TD
    A[Payment request] --> B{Card network?}
    B -->|VISA| C{Acquirer supports VPP?}
    B -->|MASTERCARD| D{MC Passkey enabled?}
    B -->|RUPAY| E[Passkey NOT supported]
    
    C -->|Yes| F{COFT transaction?}
    C -->|No| E
    
    D -->|Yes| G{COFT transaction?}
    D -->|No| E
    
    F -->|Yes| H{Merchant enrolled for VPP?}
    F -->|No| I[Passkey requires COFT]
    
    G -->|Yes| J{Merchant enrolled for MC Passkey?}
    G -->|No| I
    
    H -->|Yes| K[ELIGIBLE for Visa Passkey]
    H -->|No| E
    
    J -->|Yes| L[ELIGIBLE for MC Passkey]
    J -->|No| E
```

## Activity Diagram - Complete Passkey Lifecycle

```mermaid
flowchart TB
    subgraph Enrollment["Passkey Enrollment (First Use)"]
        E1[Customer completes first payment] --> E2[3DS challenge completed]
        E2 --> E3[Payment authorized successfully]
        E3 --> E4[Offer passkey binding]
        E4 --> E5{Customer accepts?}
        E5 -->|Yes| E6[Redirect to Visa/MC binding page]
        E6 --> E7[Customer creates FIDO2 credential]
        E7 --> E8[Passkey registered with PAR]
        E5 -->|No| E9[Skip - normal flow continues]
    end

    subgraph Authentication["Passkey Authentication (Subsequent)"]
        A1[Customer initiates payment] --> A2[Extended landing page loads]
        A2 --> A3[SDK collects device data]
        A3 --> A4[Passkey lookup by PAR]
        A4 --> A5{Passkey found?}
        A5 -->|ACTIVE| A6[Prompt biometric auth]
        A6 --> A7[FIDO2 assertion]
        A7 --> A8[Auth code generated]
        A8 --> A9[Frictionless authorization ECI=05]
        A5 -->|NOT_FOUND| A10[Fall back to 3DS + offer binding]
        A5 -->|SUSPENDED| A11[Fall back to 3DS]
    end

    subgraph Lifecycle["Passkey Lifecycle"]
        L1[Passkey created] --> L2[ACTIVE state]
        L2 --> L3{User action}
        L3 -->|Device lost| L4[Revoke passkey]
        L3 -->|New device| L5[Re-register passkey]
        L3 -->|Card expires| L6[Passkey remains via PAR]
    end
```

## Network-Specific Passkey Details

### Visa Payment Passkey (VPP)

| Aspect | Details |
|--------|---------|
| Protocol | FIDO2/WebAuthn via Visa Click to Pay SDK |
| Lookup Key | PAR (Payment Account Reference) |
| Auth Result | authCode (exchanged for CAVV at CYBS) |
| Binding Trigger | After successful 3DS auth |
| Binding Mode | Non-blocking (payment already done) |
| Failure Handling | Hard failure - no 3DS fallback in auth flow |

### Mastercard SRC Passkey

| Aspect | Details |
|--------|---------|
| Protocol | FIDO2/WebAuthn via MC SRC SDK |
| Lookup Key | PAR |
| Auth Result | Direct CAVV generation |
| Callback | GET /mastercard/responsehandler/{acquirer} |
| Failure Handling | Fall back to standard 3DS |

## Redirect Listener Passkey Endpoints

| Endpoint | Method | Network | Purpose |
|----------|--------|---------|---------|
| `/visa/responsehandler/{acquirer}` | POST | Visa | VPP auth completion callback |
| `/mastercard/responsehandler/{acquirer}` | GET | Mastercard | MC passkey auth callback |
| `/passkey/binding/callback/{acquirer}` | POST | Visa | Binding result (non-blocking) |

## Configuration

```sql
-- Passkey enablement in acquirer-network config
PINE_PG_ACQUIRER_NETWORK_CONFIG_TBL:
  IS_PASSKEY_ENABLED = 1
  PASSKEY_TYPE = 'VPP'  -- or 'SRC' for Mastercard
```

## Key Design Decisions

1. **COFT is prerequisite**: Passkey only works with tokenized cards (network tokens)
2. **Binding is non-blocking**: Payment completes first, then passkey enrollment is offered
3. **Auth failure is hard**: If passkey auth fails, no automatic 3DS fallback (phase 1)
4. **Network-branched logic**: Visa and MC have separate code paths at every extension point
5. **Extended landing page**: Custom HTML page that loads network SDK for device fingerprinting

## Error Scenarios

| Error | Impact | Recovery |
|-------|--------|----------|
| Passkey lookup timeout | Auth flow blocked | Fall back to 3DS |
| Biometric failed | Auth rejected | Allow retry (max 3) |
| Binding callback timeout | Non-blocking | Payment already succeeded |
| SDK load failure | Can't initiate passkey | Fall back to standard flow |
| CYBS authCode exchange fails | Authorization blocked | Fail payment |
