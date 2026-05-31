# Card Gateway Architecture - Plural Payment Platform

Complete architecture documentation for the Plural Card Payment Ecosystem covering all services, workflows, database schemas, and integration patterns.

## Table of Contents

1. [Architecture Overview](./architecture-overview.md) - High-level system design, service map, and tech stack
2. [Database Schema](./database/) - Complete ER diagrams and DDL for all card services
   - [Card Gateway DB](./database/card-gateway-schema.md)
   - [Customer Vault DB](./database/customer-vault-schema.md)
   - [Token Management DB](./database/token-management-schema.md)
   - [Native OTP DB](./database/native-otp-schema.md)
3. [Workflows](./workflows/) - Sequence and activity diagrams for every flow

## Workflow Documentation

| Workflow | Description |
|----------|-------------|
| [Payment Processing](./workflows/payment-processing.md) | Process, Authorize, Authenticate, Capture, Refund, Void |
| [COFT (Card on File Tokenization)](./workflows/coft-workflow.md) | Tokenized card payment with cryptogram generation |
| [Network Tokenization](./workflows/network-tokenization.md) | Card enrollment with Visa/MC/RuPay networks |
| [Issuer Tokenization](./workflows/issuer-tokenization.md) | Issuer-level token provisioning and lifecycle |
| [Native OTP](./workflows/native-otp.md) | Native OTP authentication for 3DS |
| [Customer Vault Management](./workflows/customer-vault-management.md) | Customer profiles, saved cards, token lifecycle |
| [Network Token Management](./workflows/network-token-management.md) | Token lifecycle, cryptograms, webhooks |
| [Network Services](./workflows/network-services.md) | Visa, Mastercard, RuPay connector operations |
| [BIN Service](./workflows/bin-service.md) | BIN lookup, token-BIN mapping, card metadata |
| [Passkey Workflow](./workflows/passkey-workflow.md) | Visa Payment Passkey (VPP) authentication & binding |
| [Redirect Listener](./workflows/redirect-listener.md) | Async callback handling for 3DS, passkey, wallets |
| [Acquirer Services](./workflows/acquirer-services.md) | Acquirer routing, connector dispatch, per-bank processing |

## Service Inventory

| Service | Tech Stack | Role |
|---------|-----------|------|
| `Plural_CardGatewayServicev21` | Java 11, Spring Boot WebFlux | Central card payment orchestrator |
| `Plural_CardConnectorService` | Java, Spring Boot WebFlux | Acquirer connector routing hub |
| `network-gateway-service` | Kotlin, Ktor | Network tokenization orchestrator |
| `nxt-customer-vault-mgm-service` | Kotlin, Ktor | Customer & card vault management |
| `nxt-token-mgm-service` | Kotlin, Ktor | Token storage & cryptogram generation |
| `native-otp-processor` | Kotlin, Ktor | Native OTP for 3DS authentication |
| `Plural_AcquirerServicev21` | Java, Spring Boot WebFlux | Acquirer config & routing data |
| `Plural_RedirectListenerv21` | Java, Spring Boot WebFlux | Async payment callback handler |
| `Plural_GlobalBINServicev21` | Java, Spring Boot WebFlux | BIN metadata resolution |
| `Plural_TokenBinMapping_Service` | Java, Spring Boot | Token-to-BIN mapping |
| `Plural_VisaNetworkConnector` | Java, Spring Boot WebFlux | Visa network operations |
| `Plural_MasterCardNetworkConnector` | Java, Spring Boot WebFlux | Mastercard network operations |
| `Plural_RupayNetworkConnector` | Java, Spring Boot WebFlux | RuPay/NPCI network operations |
| `Plural_HdfcCardConnectorService` | Java | HDFC acquirer connector |
| `Plural_CybsCardConnectorService` | Java | Cybersource acquirer connector |
| `Plural_RblCardConnectorService` | Java | RBL acquirer connector |
| `mpgs-connector-service` | Java | MPGS (Axis/Amex) connector |
| `Plural_FiservConnectorService` | Java | Fiserv acquirer connector |

## Architecture Principles

- **Central Orchestration**: Card Gateway is the single entry point for all card payment operations
- **Factory Pattern**: Connector selection via factory for both acquirer and network routing
- **Reactive Stack**: All services use non-blocking I/O (WebFlux/Ktor coroutines)
- **Event Sourcing**: NXT services use outbox pattern for event-driven consistency
- **Dual-DB Migration**: Legacy SQL Server being migrated to PostgreSQL (ADR-0002)
- **Observability**: OpenTelemetry traces, structured logging, Prometheus metrics (ADR-0003)
