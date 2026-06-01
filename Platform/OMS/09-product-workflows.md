# 09 — Product Workflows

> DCC, MCC, Cross-Border (PA-CB), EMI, Split Payments, Brand Wallet, UPI Mandate, and other specialized flows

---

## Transaction Handler Selection (Strategy Pattern)

```mermaid
flowchart TD
    A[Payment Request Arrives] --> B[TransactionHandlerFactory.getHandler]

    B --> C{MCC enabled?}
    C -->|Yes + WALLET| D[MccWalletTxnHandler]
    C -->|Yes + Other| E[MccTxnHandler]
    C -->|No| F{International card?}

    F -->|Yes + DCC config| G[DccTxnHandler]
    F -->|No| H{ICB on UPI?}

    H -->|Yes| I[ICBTxnHandler]
    H -->|No| J{CardlessEMI with PAN?}

    J -->|Yes| K[CardLessEMIHandler]
    J -->|No| L[NormalTxnHandler]

    D --> M[PaymentFlow.MCC_PAYMENT_FLOW]
    E --> M
    G --> N[PaymentFlow.REDIRECT_DCC_OPT_IN<br/>or SEAMLESS_DCC_OPT_IN]
    I --> O[PaymentFlow.ICB_ON_UPI]
    K --> P[PaymentFlow.SEAMLESS_OPT_IN]
    L --> Q[PaymentFlow.DEFAULT]
```

---

## 1. Dynamic Currency Conversion (DCC)

DCC allows international cardholders to pay in their home currency while the merchant receives INR.

### DCC Flow (Async — Redirect)

```mermaid
sequenceDiagram
    participant M as Merchant/Checkout
    participant OMS as OMS
    participant Handler as DccTxnHandler
    participant AsyncSvc as AsyncPaymentHandlerService
    participant CreditPlus as CreditPlus Service
    participant Redis as Redis Cache
    participant Checkout as Checkout UI
    participant SDK as PaymentSDK
    participant GW as Card Gateway

    M->>OMS: POST /orders/{orderId}/payments<br/>{method: CARD, cardNumber: "4111..."}
    OMS->>Handler: getHandler() → DccTxnHandler
    Handler->>AsyncSvc: handleCreatePayment()
    activate AsyncSvc

    AsyncSvc->>AsyncSvc: Validate international card (BIN check)
    AsyncSvc->>CreditPlus: getDccRates(cardNumber, amount, currency)
    CreditPlus-->>AsyncSvc: {foreignCurrency: USD, rate: 83.2,<br/>foreignAmount: 120.19}

    AsyncSvc->>Redis: Cache encrypted card details<br/>(AES encryption, TTL=15min)
    AsyncSvc->>Redis: Cache DCC details<br/>(rate, foreignAmount, foreignCurrency)

    AsyncSvc->>AsyncSvc: Generate checkout redirect URL
    AsyncSvc-->>OMS: {status: PENDING,<br/>challengeUrl: "/checkout/dcc/{paymentId}"}
    deactivate AsyncSvc

    OMS->>OMS: Mark payment AUTH_CHALLENGED
    OMS->>OMS: Mark order PENDING
    OMS-->>M: 200 {challengeUrl: "/checkout/dcc/..."}

    Note over Checkout: User sees DCC choice screen

    Checkout->>OMS: PATCH /orders/{orderId}/payments/{paymentId}/process<br/>{dccOptIn: true, selectedCurrency: USD}
    activate OMS

    OMS->>Redis: Retrieve cached card + DCC details
    OMS->>SDK: createPayment(card, dccInfo)
    SDK->>GW: Process with DCC
    GW-->>SDK: {status: PENDING, challengeUrl: "3DS..."}
    SDK-->>OMS: Response
    OMS-->>Checkout: Continue with 3DS flow
    deactivate OMS
```

### DCC Modes

| Mode | Description | Trigger |
|------|-------------|---------|
| **REDIRECT_DCC_OPT_IN** | User redirected to checkout for DCC choice | Standard international card |
| **SEAMLESS_DCC_OPT_IN** | Merchant provides DCC opt-in upfront in API | Merchant has DCC-compliant integration |

---

## 2. Multi-Currency Checkout (MCC)

MCC allows merchants to price in foreign currencies. The order amount is in foreign currency; OMS converts to INR for processing.

### MCC Flow

```mermaid
sequenceDiagram
    participant M as Merchant
    participant OMS as OMS
    participant FX as FX Rate Service
    participant SDK as PaymentSDK
    participant GW as Gateway

    M->>OMS: POST /orders<br/>{amount: 100, currency: USD, mcc: true}
    OMS->>OMS: Validate MCC currency code<br/>(lookup mcc_currency_codes table)
    OMS->>OMS: Store order with base currency USD
    OMS-->>M: {orderId, amount: 100, currency: USD}

    M->>OMS: POST /orders/{orderId}/payments<br/>{method: CARD}
    activate OMS

    OMS->>OMS: MccTxnHandler selected
    OMS->>FX: getExchangeRate(USD → INR)
    FX-->>OMS: {rate: 83.5}

    OMS->>OMS: Calculate INR amount: 100 × 83.5 = 8350
    OMS->>OMS: Store mccInfo on payment<br/>{baseCurrency: USD, baseAmount: 100, rate: 83.5}

    OMS->>SDK: createPayment(amount: 8350 INR, mccInfo)
    SDK->>GW: Process in INR
    GW-->>SDK: Response
    SDK-->>OMS: Success
    deactivate OMS
```

### MCC Validation

- Currency must exist in `mcc_currency_codes` table
- Only supported payment methods can be used with MCC
- Exchange rate is locked at payment creation time

---

## 3. Cross-Border (PA-CB)

Payment Aggregator Cross-Border flow for international trade with regulatory compliance (RBI PA-CB guidelines).

### PA-CB Flow

```mermaid
sequenceDiagram
    participant M as Merchant
    participant OMS as OMS
    participant CB as CrossBorderServiceOms
    participant TCS as TcsComputationService
    participant SDK as PaymentSDK
    participant GW as Gateway

    M->>OMS: POST /orders<br/>{amount: 50000, crossBorderDetails: {paCb: true}}
    OMS->>OMS: Mark order as PA-CB enabled

    M->>OMS: POST /orders/{orderId}/payments<br/>{payerData: {pan, passport, address}}
    activate OMS

    OMS->>CB: crossBorderPayerDataValidation(payerData)
    CB->>CB: Validate PAN format
    CB->>CB: Validate passport details
    CB->>CB: Validate address completeness
    CB-->>OMS: Validation passed

    OMS->>TCS: computeTcs(amount, payerPan)
    TCS-->>OMS: {tcsAmount: 2500, tcsRate: 5%}

    OMS->>OMS: Total = amount + TCS = 52500
    OMS->>SDK: createPayment(52500)
    SDK->>GW: Process payment
    GW-->>SDK: Response
    SDK-->>OMS: Success
    deactivate OMS
```

### PA-CB Documents (Invoice & AWB)

```mermaid
sequenceDiagram
    participant M as Merchant
    participant OMS as OMS
    participant DB as PostgreSQL

    M->>OMS: POST /orders/{orderId}/invoices<br/>{invoiceNumber, items, amount}
    OMS->>DB: INSERT pa_cb_invoices
    OMS-->>M: 200 {invoiceId, status: UPLOADED}

    M->>OMS: POST /orders/{orderId}/awb<br/>{awbNumber, courier, trackingUrl}
    OMS->>DB: INSERT pa_cb_awb_mappings
    OMS-->>M: 200 {awbId, status: UPLOADED}

    M->>OMS: GET /orders/{orderId}/invoices/{invoiceId}
    OMS->>DB: SELECT FROM pa_cb_invoices
    OMS-->>M: {invoice details}
```

---

## 4. EMI (Equated Monthly Installments)

### EMI Types

| Type | Description | Gateway |
|------|-------------|---------|
| **CREDIT_EMI** | EMI on credit card | Affordability Gateway |
| **DEBIT_EMI** | EMI on debit card | Affordability Gateway |
| **CARDLESS_EMI** | EMI without card (PAN-based) | Affordability Gateway (async) |
| **BNPL** | Buy Now Pay Later | Affordability Gateway |

### Credit EMI Flow

```mermaid
sequenceDiagram
    participant M as Merchant
    participant OMS as OMS
    participant Offer as Offer Service
    participant SDK as PaymentSDK
    participant AGW as Affordability Gateway
    participant Lender as EMI Lender

    M->>OMS: POST /orders/{orderId}/payments<br/>{method: CREDIT_EMI, tenure: 6,<br/>offerId: "offer_xxx"}
    activate OMS

    OMS->>OMS: Validate offer eligibility
    OMS->>SDK: createPayment(CREDIT_EMI, tenure=6)
    SDK->>AGW: EMI authorization
    AGW->>Lender: Process EMI
    Lender-->>AGW: Authorized
    AGW-->>SDK: {status: PROCESSED}
    SDK-->>OMS: Success

    OMS->>Offer: confirmOffer(orderId, offerId)
    Offer-->>OMS: {status: APPROVED}

    OMS->>OMS: Mark payment CAPTURED
    OMS->>OMS: Mark order PROCESSED
    OMS-->>M: 200 {status: PROCESSED}
    deactivate OMS
```

### Cardless EMI Flow (Async)

```mermaid
sequenceDiagram
    participant M as Merchant
    participant OMS as OMS
    participant Handler as CardLessEMIHandler
    participant AsyncSvc as AsyncPaymentHandlerService
    participant Redis as Redis
    participant Checkout as Checkout UI
    participant SDK as PaymentSDK
    participant AGW as Affordability Gateway

    M->>OMS: POST /orders/{orderId}/payments<br/>{method: CARDLESS_EMI, pan: "XXXXX1234X"}
    OMS->>Handler: CardLessEMIHandler selected
    Handler->>AsyncSvc: handleCreatePayment()

    AsyncSvc->>Redis: Cache PAN + offer details
    AsyncSvc-->>OMS: {challengeUrl: "/checkout/emi/{paymentId}"}
    OMS-->>M: 200 {status: PENDING, challengeUrl}

    Note over Checkout: User selects tenure, enters OTP

    Checkout->>OMS: PATCH /payments/{paymentId}/process<br/>{tenure: 6, otp: "123456"}
    OMS->>Redis: Retrieve cached details
    OMS->>SDK: createPayment(CARDLESS_EMI)
    SDK->>AGW: Process
    AGW-->>SDK: Success
    OMS->>OMS: Mark PROCESSED
```

### Offer Confirmation Failure

If the offer service rejects the offer after payment authorization:

```mermaid
sequenceDiagram
    participant OMS as OMS
    participant Offer as Offer Service
    participant SDK as PaymentSDK

    OMS->>Offer: confirmOffer(orderId, offerId)
    Offer-->>OMS: {status: NOT_APPROVED}

    Note over OMS: Offer rejected → must reverse payment

    OMS->>OMS: Mark payment (keep current state)
    OMS->>SDK: refundPayment() or voidPayment()
    SDK-->>OMS: Reversed

    OMS->>OMS: Mark order as per reversal
```

---

## 5. Split Payments (Part Payment)

Multiple payments on a single order using different methods.

### Split Payment Flow

```mermaid
sequenceDiagram
    participant M as Merchant
    participant OMS as OMS
    participant SDK as PaymentSDK

    M->>OMS: POST /orders<br/>{amount: 10000, partPayment: true}
    OMS-->>M: {orderId, status: CREATED}

    %% First payment
    M->>OMS: POST /orders/{orderId}/payments<br/>{method: CARD, amount: 6000}
    OMS->>SDK: createPayment(CARD, 6000)
    SDK-->>OMS: Authorized (pre-auth)
    OMS->>OMS: Payment 1 AUTHORIZED
    OMS->>OMS: Order still AUTHORIZED (partial)
    OMS-->>M: {paymentId: pay_1, status: AUTHORIZED}

    %% Second payment
    M->>OMS: POST /orders/{orderId}/payments<br/>{method: UPI, amount: 4000}
    OMS->>SDK: createPayment(UPI, 4000)
    Note over SDK: UPI collect sent
    SDK-->>OMS: PENDING
    OMS-->>M: {paymentId: pay_2, status: PENDING}

    Note over OMS: UPI callback arrives
    OMS->>OMS: Payment 2 AUTHORIZED

    %% Both authorized → auto-authorize pending
    OMS->>OMS: authorizePendingPayments()
    OMS->>OMS: All payments authorized
    OMS->>OMS: Order status: AUTHORIZED

    %% Capture
    M->>OMS: PUT /orders/{orderId}/capture
    OMS->>SDK: capture(pay_1, 6000)
    OMS->>SDK: capture(pay_2, 4000)
    OMS->>OMS: Order PROCESSED
```

### Split Payment Rules

| Rule | Description |
|------|-------------|
| Amount validation | Sum of payment amounts must equal order amount |
| Partial capture | Not allowed for split (must capture all or none) |
| Convenience fee | Feature fee validated per payment |
| Capture priority | CARD captured first, then others |
| Cancel one payment | Cancels only that payment, order stays open |

---

## 6. Brand Wallet (Add Money)

Brand wallet top-up uses `ADD_MONEY` order type.

```mermaid
sequenceDiagram
    participant BW as Brand Wallet Service
    participant OMS as OMS
    participant SDK as PaymentSDK
    participant GW as Brand Wallet Gateway

    BW->>OMS: POST /api/internal/brand-wallet/orders<br/>{type: ADD_MONEY, amount: 5000}
    OMS->>OMS: Create ADD_MONEY order

    BW->>OMS: POST /orders/{orderId}/payments<br/>{method: BRAND_WALLET}
    OMS->>SDK: addMoneyToBrandWallet(amount)
    SDK->>GW: Top-up request
    GW-->>SDK: Success
    SDK-->>OMS: PROCESSED

    OMS->>OMS: Mark CAPTURED + PROCESSED
    OMS-->>BW: Success
```

---

## 7. UPI Mandate (Recurring Payments)

UPI mandates allow automatic debits on a recurring basis.

### Mandate Creation Flow

```mermaid
sequenceDiagram
    participant M as Merchant
    participant OMS as OMS
    participant SDK as PaymentSDK
    participant UPI as UPI Gateway

    M->>OMS: POST /orders/{orderId}/payments<br/>{method: UPI, mandateInfo: {<br/>  type: CREATE_MANDATE,<br/>  maxAmount: 10000,<br/>  frequency: MONTHLY<br/>}}
    OMS->>SDK: createPayment(UPI mandate)
    SDK->>UPI: Create mandate request
    UPI-->>SDK: {mandateId, collectUrl}
    SDK-->>OMS: PENDING

    Note over UPI: User approves mandate in UPI app

    UPI->>OMS: Callback: mandate created
    OMS->>OMS: Process CREATE_MANDATE callback
    OMS->>OMS: Mark AUTHORIZED (mandate active)
```

### Mandate Execution Flow

```mermaid
sequenceDiagram
    participant M as Merchant
    participant OMS as OMS
    participant SDK as PaymentSDK
    participant UPI as UPI Gateway

    M->>OMS: POST /orders/{orderId}/payments<br/>{method: UPI, mandateInfo: {<br/>  type: EXECUTE_MANDATE,<br/>  mandateId: "mdt_xxx",<br/>  amount: 999<br/>}}
    OMS->>SDK: createPayment(execute mandate)
    SDK->>UPI: Execute debit
    UPI-->>SDK: {status: PROCESSED}
    SDK-->>OMS: Success
    OMS->>OMS: Mark CAPTURED + PROCESSED
```

---

## 8. ICB on UPI (Instant Cashback)

Instant cashback on UPI payments — handled by a dedicated service.

```mermaid
sequenceDiagram
    participant M as Merchant
    participant OMS as OMS
    participant ICB as ICB Payment Service
    participant UPI as UPI Gateway

    M->>OMS: POST /orders/{orderId}/payments<br/>{method: UPI, icbEligible: true}
    OMS->>OMS: ICBTxnHandler selected
    OMS->>ICB: processPayment(order, payment)
    ICB->>UPI: Create UPI collect with ICB
    UPI-->>ICB: Pending
    ICB-->>OMS: {status: PENDING}
    OMS-->>M: {status: PENDING}

    Note over UPI: User pays, cashback applied instantly
```

---

## 9. Convenience Fee

Convenience fee can be charged on top of the order amount.

```mermaid
sequenceDiagram
    participant M as Merchant
    participant OMS as OMS
    participant ConFee as Convenience Fee Service
    participant SDK as PaymentSDK

    M->>OMS: POST /orders/{orderId}/payments<br/>{method: CARD, convenienceFee: {amount: 50}}
    activate OMS

    OMS->>ConFee: validateConvenienceFee(merchantId, method, amount)
    ConFee-->>OMS: Valid (matches merchant config)

    OMS->>OMS: Total charge = orderAmount + convenienceFee
    OMS->>OMS: Store convenienceFeeBreakdown on payment

    OMS->>SDK: createPayment(totalAmount)
    SDK-->>OMS: Success
    deactivate OMS
```

### Post-Auth Convenience Fee (UPI)

For UPI, convenience fee is resolved after successful payment:

```mermaid
sequenceDiagram
    participant UPI as UPI Gateway
    participant OMS as OMS
    participant ConFee as Convenience Fee Service

    UPI->>OMS: processPayment(status: PROCESSED)
    OMS->>OMS: Payment method = UPI
    OMS->>ConFee: getPostAuthConFee(payment)
    ConFee-->>OMS: {convenienceFee: 25}
    OMS->>OMS: Store postAuthConFee on payment
    OMS->>OMS: Mark CAPTURED with fee details
```

---

## 10. Native OTP (Card)

For cards enrolled in native OTP (bypassing bank ACS page):

```mermaid
sequenceDiagram
    participant M as Merchant
    participant OMS as OMS
    participant OTP as Native OTP Service
    participant SDK as PaymentSDK
    participant GW as Card Gateway

    M->>OMS: POST /orders/{orderId}/payments<br/>{method: CARD, nativeOtp: true}
    OMS->>SDK: createPayment(card)
    SDK->>GW: Initiate (native OTP)
    GW-->>SDK: {otpRequired: true, otpLength: 6}
    SDK-->>OMS: AUTH_CHALLENGED (OTP required)
    OMS-->>M: {status: PENDING, otpRequired: true}

    M->>OMS: POST /orders/{orderId}/otp/submit<br/>{otp: "123456"}
    OMS->>OTP: submitOtp(paymentId, otp)
    OTP->>GW: Submit OTP
    GW-->>OTP: Authorized
    OTP-->>OMS: Success

    OMS->>OMS: Mark CAPTURED + PROCESSED
    OMS-->>M: {status: PROCESSED}
```
