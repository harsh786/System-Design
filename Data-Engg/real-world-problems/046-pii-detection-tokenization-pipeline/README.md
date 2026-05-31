# Problem 46: PII Detection & Tokenization Pipeline

### Problem 46: PII Detection & Tokenization Pipeline
```
ARCH: Data → NER model (detect PII) → Tokenize/Hash → Store
DETECTION: Names, emails, SSN, phone, address (NLP + regex)
TOKENIZATION: Format-preserving encryption (FPE) for testing
GDPR: Right to erasure = delete token mapping = data "forgotten"
```
