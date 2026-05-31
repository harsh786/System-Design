  Current context :
1. Current architecture Diagram /Users/harsh.kumar01/Documents/dev/plural/Platform/CurrentContextGiven.md
2. Merchant——>Kong——>OMS——>Postgres DB———>Debizium —firehose(generic consumer by haystack)——>OHS
   3.  OMS——>Nxt internal contract repo is used for having merchant facing contracts
   4. To Storing params in OHS, next msg contract is used which have contracts in proto format
  5.   Scrap all merchant facing contracts from https://developer.pinelabsonline.com/reference/
   6. For more context on merchant facing contract: Fetch it from GitHub https://github.com/Plural-Pvt/plural-nxt-api-contracts-internal
   7. For more context on data save in OHS, protocol contract refer: https://github.com/Plural-Pvt/nxt-message-contracts
   8. For OMS context refer the : /Users/harsh.kumar01/Documents/dev/plural/Platform/CLAUDE.md

Context from Repositories:
1. OMS: https://github.com/Plural-Pvt/nxt_payment_order_service
2. Merchant Contracts: ttps://github.com/Plural-Pvt/plural-nxt-api-contracts-internal
3. Internal Message Proto Contracts:   https://github.com/Plural-Pvt/nxt-message-contracts
4. Fx rate Service https://github.com/Plural-Pvt/repo-fx-rate-service
5. Dashboard Backend: https://github.com/Plural-Pvt/dashboard-bff
6. Merchant Service: https://github.com/Plural-Pvt/Plural_MerchantServicev21
7. Webhook Service: https://github.com/Plural-Pvt/webhook-service
8. Settlement Service: https://github.com/Plural-Pvt/nxt-settlement
9. Order history Service:  https://github.com/Plural-Pvt/nxt_order_history_service

Refer the image for current architecture: /Users/harsh.kumar01/Documents/learning/AGENTS/Tech-Solutioning-Agent/Plural-Context/Architecture.jpg