# Redirect Listener Service

## Overview

The Redirect Listener (`Plural_RedirectListenerv21`) is the central callback handler for all asynchronous payment flows. When a customer completes authentication at an external page (3DS, passkey, wallet, netbanking), the bank/network POSTs back to the Redirect Listener, which then orchestrates the next steps (authorization, binding, merchant redirect).

## Services Involved

| Service | Role |
|---------|------|
| Redirect Listener | Receives all async payment callbacks |
| OMS | Triggers authorization after authentication |
| Card Gateway | Process/authorize endpoints |
| Edge Cache (Redis) | Payment session data |
| Merchant | Final redirect destination |

## Architecture

```mermaid
graph TB
    subgraph External["External Callback Sources"]
        ACS[Issuer ACS<br/>3DS Authentication]
        VPP[Visa VPP<br/>Passkey Auth]
        MCSRC[MC SRC<br/>Passkey Auth]
        Wallet[Wallets<br/>PhonePe/Paytm]
        NB[Netbanking<br/>Banks]
        BNPL[BNPL<br/>Simpl/LazyPay]
        RuPay[RuPay<br/>Network Auth]
    end

    subgraph RL["Redirect Listener Service"]
        MainCtrl[RedirectListenerController<br/>3DS callbacks]
        PasskeyCtrl[PasskeyRedirectListenerController<br/>Visa/MC passkey]
        MCCtrl[MastercardRedirectListenerController]
        RupayCtrl[RupayCallbackController]
        WalletCtrl[WalletRedirectListenerController]
        NBCtrl[NetbankingRedirectListenerController]
        BNPLCtrl[BnplRedirectListenerController]
    end

    subgraph Internal["Internal Services"]
        OMS[Order Management]
        CGW[Card Gateway]
        Cache[(Edge Cache<br/>Redis)]
    end

    subgraph Merchant["Merchant"]
        ReturnURL[Merchant Return URL]
    end

    ACS --> MainCtrl
    VPP --> PasskeyCtrl
    MCSRC --> PasskeyCtrl
    Wallet --> WalletCtrl
    NB --> NBCtrl
    BNPL --> BNPLCtrl
    RuPay --> RupayCtrl

    MainCtrl --> Cache
    MainCtrl --> OMS
    PasskeyCtrl --> OMS & CGW
    
    OMS --> CGW
    
    MainCtrl --> ReturnURL
    PasskeyCtrl --> ReturnURL
    WalletCtrl --> ReturnURL
    NBCtrl --> ReturnURL
    BNPLCtrl --> ReturnURL
```

## 3DS Redirect Callback Sequence

```mermaid
sequenceDiagram
    participant Browser as Customer Browser
    participant ACS as Issuer ACS Page
    participant RL as Redirect Listener
    participant Cache as Edge Cache (Redis)
    participant OMS as Order Management
    participant CGW as Card Gateway
    participant Merchant as Merchant URL

    Note over Browser: Customer completes<br/>3DS challenge (OTP/biometric)

    ACS->>RL: POST /redirect (paRes, MD/threeDSSessionData)
    
    RL->>Cache: Fetch EdgeCacheData by payment session
    Cache-->>RL: Payment context (merchant_id, order_id, acquirer, return_url)
    
    RL->>RL: Decode paRes/cRes
    RL->>RL: Extract authentication result

    RL->>OMS: Trigger authorization (payment_id, auth_data)
    OMS->>CGW: POST /authorize (CAVV, ECI, auth_status)
    CGW-->>OMS: Authorization result
    OMS-->>RL: Payment status

    RL-->>Browser: HTTP 302 Redirect to merchant return URL
    Browser->>Merchant: GET /return?payment_id=X&status=success
```

## Visa Passkey Callback Sequence

```mermaid
sequenceDiagram
    participant Browser as Customer Browser
    participant Visa as Visa VPP
    participant RL as Redirect Listener
    participant OMS as Order Management
    participant CGW as Card Gateway
    participant Merchant as Merchant URL

    Note over Browser: Customer completes<br/>biometric auth at Visa

    Visa->>RL: POST /visa/responsehandler/{acquirer}
    Note over RL: Form POST with:<br/>authorizationCode, status

    RL->>RL: Extract authCode from Visa callback
    RL->>OMS: Trigger authorization with authCode
    OMS->>CGW: POST /authorize (authCode, frictionless)
    
    Note over CGW: Exchange authCode at CYBS<br/>for CAVV + ECI=05

    CGW-->>OMS: AUTHORIZED
    OMS-->>RL: Success

    RL-->>Browser: Redirect to merchant return URL
```

## Passkey Binding Callback Sequence

```mermaid
sequenceDiagram
    participant Browser as Customer Browser
    participant Visa as Visa VPP
    participant RL as Redirect Listener
    participant Merchant as Merchant URL

    Note over Browser: Passkey binding UI shown<br/>after successful payment

    alt Customer creates passkey
        Browser->>Visa: Register FIDO2 credential
        Visa->>RL: POST /passkey/binding/callback/{acquirer} (success)
        Note over RL: Non-blocking<br/>Payment already done
        RL-->>Browser: Redirect to merchant
    else Customer skips
        Browser->>Visa: Skip binding
        Visa->>RL: POST /passkey/binding/callback/{acquirer} (skipped)
        RL-->>Browser: Redirect to merchant
    end

    Browser->>Merchant: GET /return?payment_id=X&status=success
```

## RuPay Callback Sequence

```mermaid
sequenceDiagram
    participant Browser as Customer Browser
    participant NPCI as RuPay/NPCI
    participant RL as Redirect Listener
    participant Cache as Edge Cache
    participant OMS as Order Management

    NPCI->>RL: POST /rupay/callback (auth response)
    
    RL->>Cache: Fetch payment session
    Cache-->>RL: Payment context
    
    RL->>RL: Parse RuPay auth response
    RL->>OMS: Authorize payment
    OMS-->>RL: Result
    
    RL-->>Browser: Redirect to merchant
```

## Activity Diagram - Redirect Listener Decision Flow

```mermaid
flowchart TD
    A[Callback received at RL] --> B{Which controller?}
    
    B -->|3DS /redirect| C[Parse paRes/cRes]
    B -->|Visa passkey| D[Extract authCode]
    B -->|MC passkey| E[Extract MC auth data]
    B -->|RuPay| F[Parse RuPay response]
    B -->|Wallet| G[Parse wallet callback]
    B -->|Netbanking| H[Parse NB response]
    B -->|BNPL| I[Parse BNPL response]
    B -->|Passkey binding| J[Non-blocking binding result]
    
    C --> K[Fetch EdgeCacheData]
    D --> K
    E --> K
    F --> K
    G --> K
    H --> K
    I --> K
    
    K --> L{Session valid?}
    L -->|No| M[Return error page]
    L -->|Yes| N[Trigger authorization via OMS]
    
    N --> O{Authorization success?}
    O -->|Yes| P[Redirect to merchant<br/>success URL]
    O -->|No| Q[Redirect to merchant<br/>failure URL]
    
    J --> R[Log binding result]
    R --> P
```

## Controller Endpoint Reference

### Main 3DS Controller (`RedirectListenerController`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/redirect` | Standard 3DS paRes callback |
| POST | `/3ds2/redirect` | 3DS2 cRes callback |
| POST | `/redirect/{acquirer}` | Acquirer-specific 3DS callback |

### Passkey Controller (`PasskeyRedirectListenerController`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/visa/responsehandler/{acquirer}` | Visa VPP auth callback |
| GET | `/mastercard/responsehandler/{acquirer}` | MC passkey auth callback |
| POST | `/passkey/binding/callback/{acquirer}` | Visa passkey binding result |

### Mastercard Controller (`MastercardRedirectListenerController`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/mastercard/redirect` | MC-specific redirect |

### RuPay Controller (`RupayCallbackController`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/rupay/callback` | RuPay auth callback |
| POST | `/rupay/s2s/callback` | RuPay server-to-server callback |

### Wallet Controller (`WalletRedirectListenerController`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/wallet/callback` | Wallet payment callback |
| POST | `/wallet/redirect/{provider}` | Provider-specific redirect |

### Netbanking Controller (`NetbankingRedirectListenerController`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/netbanking/callback` | Netbanking auth callback |

### BNPL Controller (`BnplRedirectListenerController`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/bnpl/callback` | BNPL auth callback |

## Edge Cache Data Structure

```json
{
  "payment_id": "PAY_123456",
  "order_id": "ORD_789",
  "merchant_id": "M001",
  "acquirer_id": "HDFC",
  "amount": 1000.00,
  "currency": "INR",
  "card_hash": "sha256...",
  "return_url": "https://merchant.com/return",
  "cancel_url": "https://merchant.com/cancel",
  "webhook_url": "https://merchant.com/webhook",
  "enrollment_data": {
    "acs_url": "https://acs.bank.com/auth",
    "pareq": "...",
    "md": "...",
    "three_ds_version": "2.2"
  },
  "acquirer_mid": "MID_001",
  "acquirer_tid": "TID_001",
  "created_at": "2024-01-01T10:00:00Z",
  "ttl_seconds": 900
}
```

## Error Handling

| Error | Handling |
|-------|----------|
| Session expired (TTL) | Show error page, redirect to merchant with failure |
| Invalid paRes/signature | Reject, log security event |
| OMS authorization timeout | Retry once, then fail to merchant |
| Merchant return URL unreachable | Log error, show payment status page |
| Duplicate callback | Idempotent - return same result |
| Missing EdgeCacheData | Return 400, log data inconsistency |

## Security

- All callback URLs are HTTPS only
- HMAC/signature validation on callbacks where supported
- EdgeCacheData has TTL (15 minutes default)
- Rate limiting on callback endpoints
- IP whitelisting for known bank/network IPs (optional)
