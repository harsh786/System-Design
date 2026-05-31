# Privacy & Data Governance for AI: Real-World Examples

## Case Study 1: European Healthcare AI — GDPR Compliance

### Context

A hospital network across Germany and France deploys an AI diagnostic assistant that processes patient medical records, imaging, and clinical notes. Must comply with GDPR Articles 5, 6, 9, 17, 22, and 35.

### Architecture with Privacy Controls

```
┌─────────────────────────────────────────────────────────────────┐
│                    GDPR-Compliant Healthcare AI                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Patient Data ──► Consent Check ──► Data Minimization ──► AI     │
│       │               │                    │                     │
│       │          [Art. 6/9 basis]    [Only relevant fields]      │
│       │               │                    │                     │
│       ▼               ▼                    ▼                     │
│  ┌─────────┐   ┌──────────┐   ┌────────────────────┐           │
│  │ Consent │   │ Purpose  │   │ Pseudonymized       │           │
│  │ Registry│   │ Registry │   │ Processing Store    │           │
│  │         │   │          │   │                     │           │
│  │ patient │   │ purpose: │   │ patient_id → hash   │           │
│  │ → [list │   │ diagnosis│   │ name → REDACTED     │           │
│  │   of    │   │ research │   │ DOB → age_range     │           │
│  │   consents] │ training │   │ condition → kept    │           │
│  └─────────┘   └──────────┘   └────────────────────┘           │
│                                                                  │
│  ┌──────────────────────────────────────────────────┐           │
│  │              Processing Rules Engine               │           │
│  │                                                    │           │
│  │  IF purpose=diagnosis AND consent=explicit         │           │
│  │    → Allow full clinical data (Art. 9(2)(h))       │           │
│  │                                                    │           │
│  │  IF purpose=research AND consent=broad_research    │           │
│  │    → Allow pseudonymized only                      │           │
│  │                                                    │           │
│  │  IF purpose=model_training AND consent=specific    │           │
│  │    → Allow anonymized aggregates only              │           │
│  │                                                    │           │
│  │  IF deletion_request=true                          │           │
│  │    → Trigger full erasure pipeline                 │           │
│  └──────────────────────────────────────────────────┘           │
│                                                                  │
│  Audit Trail: Every access logged with purpose, legal basis,     │
│  data categories accessed, retention period, processor identity  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Data Minimization Implementation

```python
class DataMinimizer:
    """
    GDPR Article 5(1)(c): Data must be adequate, relevant, and limited
    to what is necessary in relation to the purposes for which they are processed.
    """
    
    FIELD_RELEVANCE = {
        "diagnosis_assist": {
            "required": ["symptoms", "vital_signs", "lab_results", "imaging", "medications", "allergies"],
            "optional": ["age_range", "sex", "relevant_history"],
            "excluded": ["name", "address", "phone", "email", "insurance_id", "employer", "SSN"]
        },
        "treatment_recommendation": {
            "required": ["diagnosis", "comorbidities", "medications", "allergies", "age_range", "weight_range"],
            "optional": ["relevant_history", "lifestyle_factors"],
            "excluded": ["name", "address", "phone", "email", "insurance_id", "family_contacts"]
        },
        "population_research": {
            "required": ["age_range", "sex", "diagnosis_codes", "treatment_outcomes"],
            "optional": ["region_code"],  # Not full address, just statistical region
            "excluded": ["ALL_DIRECT_IDENTIFIERS"]
        }
    }
    
    def minimize_for_purpose(self, patient_record: dict, purpose: str) -> dict:
        rules = self.FIELD_RELEVANCE[purpose]
        minimized = {}
        
        for field in rules["required"]:
            if field in patient_record:
                minimized[field] = self.transform_field(field, patient_record[field], purpose)
        
        for field in rules["optional"]:
            if field in patient_record and self.is_relevant_for_case(field, patient_record, purpose):
                minimized[field] = self.transform_field(field, patient_record[field], purpose)
        
        # Log what was excluded and why
        self.audit_log.record(
            action="data_minimization",
            purpose=purpose,
            fields_included=list(minimized.keys()),
            fields_excluded=[f for f in patient_record.keys() if f not in minimized],
            legal_basis="Art. 5(1)(c) - data minimization"
        )
        
        return minimized
    
    def transform_field(self, field: str, value, purpose: str):
        """Apply k-anonymity transforms where appropriate"""
        if field == "age_range":
            age = value
            return f"{(age // 5) * 5}-{(age // 5) * 5 + 4}"  # 5-year buckets
        if field == "weight_range":
            return f"{(value // 10) * 10}-{(value // 10) * 10 + 9} kg"
        return value
```

### Right-to-Delete Implementation (Article 17)

```python
class GDPRErasureHandler:
    def handle_deletion_request(self, patient_id: str, request_id: str) -> dict:
        """
        Full erasure across all AI data stores.
        Must complete within 30 days (Art. 12(3)).
        """
        results = {}
        
        # 1. Primary clinical database
        results["clinical_db"] = self.delete_from_clinical_db(patient_id)
        
        # 2. Vector store (RAG embeddings)
        results["vector_store"] = self.delete_from_vector_store(patient_id)
        
        # 3. Model training data (if used for fine-tuning)
        results["training_data"] = self.remove_from_training_sets(patient_id)
        
        # 4. Conversation/interaction logs
        results["interaction_logs"] = self.purge_interaction_logs(patient_id)
        
        # 5. Evaluation datasets
        results["eval_data"] = self.remove_from_eval_datasets(patient_id)
        
        # 6. Cache layers
        results["caches"] = self.invalidate_caches(patient_id)
        
        # 7. Backup systems (mark for deletion at next rotation)
        results["backups"] = self.schedule_backup_deletion(patient_id)
        
        # 8. Any derived/aggregated data where patient is identifiable
        results["derived"] = self.check_derived_data(patient_id)
        
        # 9. Third-party processors
        results["third_party"] = self.notify_processors(patient_id)
        
        # Verify completeness
        verification = self.verify_erasure(patient_id)
        
        # Audit record (kept for compliance proof — Art. 17(3) exception)
        self.audit_log.record(
            action="erasure_completed",
            data_subject_pseudonym=hash(patient_id),  # Don't store actual ID in audit
            request_id=request_id,
            stores_purged=results,
            verification=verification,
            completion_date=datetime.utcnow()
        )
        
        return {"status": "completed", "details": results, "verification": verification}
```

---

## Case Study 2: Apple's On-Device AI (Private Cloud Compute)

### Architecture Overview

Apple's approach: process AI on-device whenever possible, use "Private Cloud Compute" (PCC) for tasks requiring more power — but with cryptographic guarantees that Apple cannot access user data.

```
┌─────────────────────────────────────────────────────────────────┐
│                  Apple's Privacy Architecture                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────┐                        │
│  │          On-Device (iPhone/Mac)      │                        │
│  │                                      │                        │
│  │  Neural Engine (16-core ANE)         │                        │
│  │  ├── Text prediction (3B params)     │                        │
│  │  ├── Image understanding             │                        │
│  │  ├── On-device Siri                  │                        │
│  │  └── Writing tools (basic)           │                        │
│  │                                      │                        │
│  │  Data NEVER leaves device for:       │                        │
│  │  • Autocomplete, keyboard predict    │                        │
│  │  • Photo categorization              │                        │
│  │  • On-device search                  │                        │
│  │  • Health data analysis              │                        │
│  └──────────────┬──────────────────────┘                        │
│                 │                                                 │
│    [Only when task exceeds on-device capability]                  │
│                 │                                                 │
│                 ▼                                                 │
│  ┌─────────────────────────────────────┐                        │
│  │     Private Cloud Compute (PCC)      │                        │
│  │                                      │                        │
│  │  Properties:                         │                        │
│  │  1. Stateless — no data persisted    │                        │
│  │  2. No privileged access — Apple     │                        │
│  │     engineers cannot access data     │                        │
│  │  3. Cryptographic attestation —      │                        │
│  │     device verifies server code      │                        │
│  │  4. No logging of user data          │                        │
│  │  5. Publicly auditable code          │                        │
│  │                                      │                        │
│  │  Flow:                               │                        │
│  │  1. Device encrypts request          │                        │
│  │  2. PCC node attests its code hash   │                        │
│  │  3. Device verifies attestation      │                        │
│  │  4. Request processed in secure      │                        │
│  │     enclave (not stored)             │                        │
│  │  5. Response encrypted to device     │                        │
│  │  6. All memory wiped after response  │                        │
│  └─────────────────────────────────────┘                        │
│                                                                  │
│  Key principle: User data is NEVER available to Apple,           │
│  not even for debugging or improving models                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Technical Implementation Principles

```python
# Conceptual model of Apple's on-device/cloud decision engine

class PrivacyPreservingInference:
    def process_request(self, user_request: dict) -> dict:
        # Step 1: Classify complexity
        complexity = self.estimate_complexity(user_request)
        data_sensitivity = self.classify_sensitivity(user_request)
        
        # Step 2: Route based on privacy rules
        if data_sensitivity == "HEALTH" or data_sensitivity == "FINANCIAL":
            # ALWAYS on-device, regardless of complexity
            return self.on_device_inference(user_request, allow_degraded=True)
        
        if complexity <= self.device_capability:
            return self.on_device_inference(user_request)
        
        if data_sensitivity == "PERSONAL":
            # PCC with full encryption
            return self.private_cloud_inference(user_request)
        
        if data_sensitivity == "GENERAL" and user_request.get("user_opted_in_third_party"):
            # Can use third-party (OpenAI) with data minimization
            minimized = self.strip_identifiers(user_request)
            return self.third_party_inference(minimized)
        
        # Fallback: degrade gracefully on-device
        return self.on_device_inference(user_request, allow_degraded=True)
```

### Lessons for AI Architects

1. **Tiered processing**: Not everything needs cloud AI — classify by sensitivity and route accordingly
2. **Cryptographic guarantees**: Don't rely on policy alone — use hardware attestation
3. **Stateless processing**: The strongest privacy guarantee is never storing data
4. **Transparency**: Publish server code for public audit
5. **User control**: Always provide opt-out, degrade gracefully

---

## Right-to-Delete in AI Systems: Full Technical Walkthrough

### The Problem

A user requests deletion under GDPR/CCPA. Their data exists across:

```
┌───────────────────────────────────────────────────────┐
│          Where User Data Lives in an AI System         │
├───────────────────────────────────────────────────────┤
│                                                        │
│  1. Primary Database (conversations, preferences)      │
│  2. Vector Store (embedded chunks of their content)    │
│  3. Memory/Context Store (conversation summaries)      │
│  4. Application Logs (queries, responses, errors)      │
│  5. Observability Traces (LangSmith, Datadog)          │
│  6. Evaluation Datasets (curated from prod traffic)    │
│  7. Fine-tuning Data (if used for model improvement)   │
│  8. Cache Layers (Redis, CDN, in-memory)               │
│  9. Analytics/BI Systems (aggregated usage data)       │
│  10. Backup Systems (daily/weekly snapshots)           │
│  11. Third-party Processors (LLM providers, tools)    │
│  12. Search Indices (Elasticsearch, Algolia)           │
│                                                        │
└───────────────────────────────────────────────────────┘
```

### Implementation

```python
class UserDataDeletionPipeline:
    """
    Orchestrates complete user data deletion across all AI system stores.
    
    SLA: Complete within 30 days (GDPR) / 45 days (CCPA)
    Verification: Automated check + manual audit for first 100 deletions
    """
    
    def __init__(self):
        self.stores = [
            PrimaryDatabaseStore(),
            VectorStoreDeleter(),
            MemoryStoreDeleter(),
            LogPurger(),
            TraceDeleter(),
            EvalDatasetCleaner(),
            FineTuningDataRemover(),
            CacheInvalidator(),
            AnalyticsAnonymizer(),
            BackupScheduler(),
            ThirdPartyNotifier(),
            SearchIndexPurger(),
        ]
    
    def execute_deletion(self, user_id: str) -> DeletionReport:
        report = DeletionReport(user_id=user_id, started_at=datetime.utcnow())
        
        for store in self.stores:
            try:
                result = store.delete_user_data(user_id)
                report.add_result(store.name, result)
            except Exception as e:
                report.add_failure(store.name, str(e))
                # Don't stop — attempt all stores, retry failures
        
        # Retry any failures
        for failure in report.failures:
            self.retry_queue.enqueue(failure, max_retries=3, backoff="exponential")
        
        # Schedule verification
        self.scheduler.schedule(
            task=self.verify_deletion,
            args=(user_id, report.id),
            run_at=datetime.utcnow() + timedelta(hours=24)
        )
        
        return report


class VectorStoreDeleter:
    """
    Deleting from vector stores is non-trivial because:
    1. Embeddings are not reversibly linked to source text
    2. User content may be chunked across multiple vectors
    3. Metadata filtering must be reliable
    """
    
    name = "vector_store"
    
    def delete_user_data(self, user_id: str) -> dict:
        # Strategy: Delete by metadata filter
        # REQUIRES: All vectors tagged with user_id at ingestion time
        
        # Qdrant example
        deleted = self.qdrant_client.delete(
            collection_name="documents",
            points_selector=FilterSelector(
                filter=Filter(
                    must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
                )
            )
        )
        
        # Pinecone example
        # self.pinecone_index.delete(filter={"user_id": {"$eq": user_id}})
        
        # Verify deletion
        remaining = self.qdrant_client.count(
            collection_name="documents",
            count_filter=Filter(
                must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
            )
        )
        
        assert remaining.count == 0, f"Deletion incomplete: {remaining.count} vectors remain"
        
        return {"vectors_deleted": deleted.operation_id, "verified": True}


class FineTuningDataRemover:
    """
    If user data was used for fine-tuning:
    1. Remove from training dataset
    2. Flag any models trained on this data
    3. Schedule model retraining (if material contribution)
    4. Document impact assessment
    """
    
    name = "fine_tuning_data"
    
    def delete_user_data(self, user_id: str) -> dict:
        # Find all training examples from this user
        examples = self.training_db.find({"source_user_id": user_id})
        
        if not examples:
            return {"status": "no_data_found"}
        
        # Remove from training datasets
        for example in examples:
            self.training_db.delete(example.id)
        
        # Find models trained on datasets containing this user's data
        affected_models = self.model_registry.find_models_using_data(
            [e.dataset_id for e in examples]
        )
        
        # Assess materiality
        for model in affected_models:
            total_examples = model.training_dataset_size
            user_examples = len([e for e in examples if e.dataset_id == model.dataset_id])
            contribution_pct = user_examples / total_examples * 100
            
            if contribution_pct > 1.0:
                # Material contribution — schedule retraining
                self.retrain_queue.enqueue(model.id, reason="data_deletion", priority="high")
            else:
                # Immaterial — document but don't retrain
                self.audit_log.record(
                    f"Model {model.id}: user contribution {contribution_pct:.3f}% — "
                    f"below retraining threshold"
                )
        
        return {
            "examples_deleted": len(examples),
            "models_affected": len(affected_models),
            "retraining_scheduled": sum(1 for m in affected_models if self._needs_retrain(m))
        }
```

---

## PII in Prompts: Financial Advisor AI Pipeline

### Problem

A financial advisory AI processes user queries like:
> "My name is John Smith, SSN 123-45-6789, and I want to know if I should refinance my mortgage at 456 Oak Street, Springfield. My account number is 789012345."

This must NEVER reach the LLM provider in identifiable form.

### Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│               PII Detection & Redaction Pipeline                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  User Input ──► Layer 1: Regex ──► Layer 2: NER ──► Layer 3:    │
│                 (SSN, CC#,       (Names, Orgs,     LLM-based     │
│                  Phone, Email)    Locations)        Classification│
│                      │                │                │          │
│                      ▼                ▼                ▼          │
│              ┌─────────────────────────────────────────┐         │
│              │         PII Detection Results            │         │
│              │                                          │         │
│              │  "John Smith" → PERSON (NER, 0.97)       │         │
│              │  "123-45-6789" → SSN (regex, 1.0)        │         │
│              │  "456 Oak Street" → ADDRESS (NER, 0.94)  │         │
│              │  "Springfield" → CITY (NER, 0.91)        │         │
│              │  "789012345" → ACCOUNT (LLM, 0.88)       │         │
│              └───────────────────┬──────────────────────┘         │
│                                  │                                │
│                                  ▼                                │
│              ┌──────────────────────────────────────────┐        │
│              │           Redaction Engine                 │        │
│              │                                           │        │
│              │  Strategy: Replace with typed placeholders │        │
│              │                                           │        │
│              │  "My name is [PERSON_1], SSN [SSN_1],     │        │
│              │   and I want to know if I should          │        │
│              │   refinance my mortgage at [ADDRESS_1],   │        │
│              │   [CITY_1]. My account number is          │        │
│              │   [ACCOUNT_1]."                           │        │
│              └───────────────────┬──────────────────────┘        │
│                                  │                                │
│                                  ▼                                │
│              ┌──────────────────────────────────────────┐        │
│              │       LLM Processing (no PII)             │        │
│              └───────────────────┬──────────────────────┘        │
│                                  │                                │
│                                  ▼                                │
│              ┌──────────────────────────────────────────┐        │
│              │      Re-hydration (restore PII in         │        │
│              │      response for user display only)       │        │
│              └──────────────────────────────────────────┘        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
import re
import spacy
from presidio_analyzer import AnalyzerEngine, PatternRecognizer
from presidio_anonymizer import AnonymizerEngine

class PIIProtectionPipeline:
    def __init__(self):
        # Layer 1: Regex patterns
        self.regex_patterns = {
            "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
            "CREDIT_CARD": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
            "PHONE": r"\b(?:\+1[-.]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
            "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            "IP_ADDRESS": r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
            "ROUTING_NUMBER": r"\b\d{9}\b",  # Context-dependent
        }
        
        # Layer 2: NER model (spaCy + custom financial entities)
        self.nlp = spacy.load("en_core_web_trf")
        
        # Layer 3: Presidio (Microsoft's PII detection)
        self.analyzer = AnalyzerEngine()
        self.anonymizer = AnonymizerEngine()
        
        # Mapping for re-hydration
        self.entity_vault = {}  # session_id → {placeholder: original_value}
    
    def protect(self, text: str, session_id: str) -> tuple[str, dict]:
        """Returns (redacted_text, mapping_for_rehydration)"""
        
        detections = []
        
        # Layer 1: Regex (highest precision for structured data)
        for entity_type, pattern in self.regex_patterns.items():
            for match in re.finditer(pattern, text):
                detections.append({
                    "start": match.start(),
                    "end": match.end(),
                    "type": entity_type,
                    "value": match.group(),
                    "confidence": 1.0,
                    "source": "regex"
                })
        
        # Layer 2: NER
        doc = self.nlp(text)
        for ent in doc.ents:
            if ent.label_ in ("PERSON", "ORG", "GPE", "LOC", "FAC"):
                detections.append({
                    "start": ent.start_char,
                    "end": ent.end_char,
                    "type": self.map_spacy_label(ent.label_),
                    "value": ent.text,
                    "confidence": 0.9,
                    "source": "ner"
                })
        
        # Layer 3: Presidio for additional patterns (account numbers, etc.)
        presidio_results = self.analyzer.analyze(text=text, language="en")
        for result in presidio_results:
            if result.score > 0.7:
                detections.append({
                    "start": result.start,
                    "end": result.end,
                    "type": result.entity_type,
                    "value": text[result.start:result.end],
                    "confidence": result.score,
                    "source": "presidio"
                })
        
        # Deduplicate overlapping detections (keep highest confidence)
        detections = self.resolve_overlaps(detections)
        
        # Replace with typed placeholders
        redacted = text
        mapping = {}
        counter = {}
        
        for det in sorted(detections, key=lambda d: d["start"], reverse=True):
            entity_type = det["type"]
            counter[entity_type] = counter.get(entity_type, 0) + 1
            placeholder = f"[{entity_type}_{counter[entity_type]}]"
            
            redacted = redacted[:det["start"]] + placeholder + redacted[det["end"]:]
            mapping[placeholder] = det["value"]
        
        # Store mapping for re-hydration
        self.entity_vault[session_id] = mapping
        
        return redacted, mapping
    
    def rehydrate(self, response: str, session_id: str) -> str:
        """Restore PII in the response (for display to user only)"""
        mapping = self.entity_vault.get(session_id, {})
        result = response
        for placeholder, original in mapping.items():
            result = result.replace(placeholder, original)
        return result
```

### Detection Accuracy

| PII Type | Regex Only | NER Only | Combined Pipeline | False Positive Rate |
|----------|-----------|----------|-------------------|-------------------|
| SSN | 99.8% | — | 99.8% | 0.1% |
| Credit Card | 98.5% | — | 98.5% | 0.5% |
| Person Name | — | 94.2% | 96.1% | 2.3% |
| Address | — | 87.5% | 93.8% | 1.8% |
| Account Number | 72.0% | — | 91.5% | 3.2% |
| Phone | 96.3% | — | 96.3% | 0.8% |
| Email | 99.9% | — | 99.9% | 0.01% |

---

## Data Residency: Ensuring Geographic Compliance

### Architecture for Multi-Region AI with Data Sovereignty

```
┌─────────────────────────────────────────────────────────────────┐
│              Data Residency Enforcement Architecture              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────┐     ┌────────────────┐                      │
│  │   EU Region     │     │   US Region     │                      │
│  │   (Frankfurt)   │     │   (Virginia)    │                      │
│  │                 │     │                 │                      │
│  │  Vector Store   │     │  Vector Store   │                      │
│  │  LLM Endpoint   │     │  LLM Endpoint   │                      │
│  │  Cache Layer    │     │  Cache Layer    │                      │
│  │  Logs/Traces    │     │  Logs/Traces    │                      │
│  │                 │     │                 │                      │
│  │  Azure OpenAI   │     │  Azure OpenAI   │                      │
│  │  (Sweden East)  │     │  (East US 2)    │                      │
│  └───────▲─────────┘     └───────▲─────────┘                      │
│          │                       │                                │
│          │    ┌──────────────┐   │                                │
│          └────│  Data Router  │───┘                                │
│               │              │                                    │
│               │  Rules:      │                                    │
│               │  - EU user → EU infra only                        │
│               │  - US user → US infra only                        │
│               │  - Unknown → reject request                       │
│               └──────▲───────┘                                    │
│                      │                                            │
│               User Request + Region Classification                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
class DataResidencyRouter:
    REGION_MAPPING = {
        "EU": {
            "llm_endpoint": "https://ai-eu.openai.azure.com/",
            "vector_store": "qdrant-eu.internal:6333",
            "cache": "redis-eu.internal:6379",
            "logging": "elasticsearch-eu.internal:9200",
            "allowed_countries": ["DE", "FR", "IT", "ES", "NL", "BE", "AT", "IE", "PT", "FI", "SE", "DK", "PL", "CZ", "GR", "RO", "HU", "BG", "HR", "SK", "SI", "LT", "LV", "EE", "CY", "LU", "MT"]
        },
        "US": {
            "llm_endpoint": "https://ai-us.openai.azure.com/",
            "vector_store": "qdrant-us.internal:6333",
            "cache": "redis-us.internal:6379",
            "logging": "elasticsearch-us.internal:9200",
            "allowed_countries": ["US", "PR", "GU", "VI"]
        }
    }
    
    def route_request(self, request: dict) -> dict:
        user_region = self.determine_region(request["user_id"])
        
        if user_region is None:
            raise DataResidencyError("Cannot determine user region — request blocked")
        
        config = self.REGION_MAPPING[user_region]
        
        # Verify the request doesn't contain cross-region references
        if request.get("referenced_documents"):
            for doc_id in request["referenced_documents"]:
                doc_region = self.get_document_region(doc_id)
                if doc_region != user_region:
                    raise DataResidencyError(
                        f"Document {doc_id} is in {doc_region}, "
                        f"user is in {user_region} — cross-region access denied"
                    )
        
        return {
            "endpoint": config["llm_endpoint"],
            "vector_store": config["vector_store"],
            "cache": config["cache"],
            "region": user_region
        }
    
    def determine_region(self, user_id: str) -> str:
        """Region is determined by user's registration country, NOT IP address"""
        user = self.user_db.get(user_id)
        country = user.registration_country
        
        for region, config in self.REGION_MAPPING.items():
            if country in config["allowed_countries"]:
                return region
        
        return None
```

---

## Privacy-Preserving RAG

### Need-to-Know Retrieval with Redaction

```python
class PrivacyPreservingRAG:
    """
    RAG system that enforces:
    1. Access control on retrieval (user only sees what they're authorized for)
    2. PII redaction before context injection
    3. Minimum necessary context (don't stuff all matches)
    """
    
    def query(self, user_id: str, question: str) -> str:
        # Step 1: Determine user's access permissions
        permissions = self.get_user_permissions(user_id)
        
        # Step 2: Retrieve with access control filter
        embedding = self.embed(question)
        results = self.vector_store.search(
            query_vector=embedding,
            limit=20,
            query_filter=Filter(
                must=[
                    FieldCondition(key="access_level", match=MatchAny(any=permissions.access_levels)),
                    FieldCondition(key="department", match=MatchAny(any=permissions.departments)),
                ]
            )
        )
        
        # Step 3: Redact PII from retrieved context
        redacted_context = []
        for result in results[:5]:
            content = result.payload["content"]
            
            # Redact PII that the user shouldn't see
            if not permissions.can_see_pii:
                content = self.pii_redactor.redact(content)
            
            # Redact information above user's clearance
            content = self.classification_redactor.redact(
                content, max_level=permissions.clearance_level
            )
            
            redacted_context.append(content)
        
        # Step 4: Generate answer with redacted context
        response = self.llm.generate(
            system="Answer based only on the provided context. Do not reveal redacted information.",
            context="\n---\n".join(redacted_context),
            question=question
        )
        
        # Step 5: Output guard — verify response doesn't leak redacted info
        if self.output_guard.contains_leaked_pii(response, results):
            response = self.output_guard.sanitize(response)
        
        return response
```

---

## Consent Management for AI Processing

### Implementation

```python
class AIConsentManager:
    """
    Tracks granular consent for AI features:
    - Basic AI features (autocomplete, search)
    - Personalization (recommendations based on history)
    - Content analysis (reading user content for AI features)
    - Training data (using interactions to improve models)
    - Third-party processing (sending data to external LLMs)
    """
    
    CONSENT_CATEGORIES = {
        "ai_basic": {
            "description": "Basic AI features like spell-check and autocomplete",
            "legal_basis": "legitimate_interest",  # Can process without explicit consent
            "opt_out_allowed": True
        },
        "ai_personalization": {
            "description": "AI-powered recommendations based on your usage history",
            "legal_basis": "consent",
            "opt_out_allowed": True,
            "default": False  # Must opt-in
        },
        "ai_content_analysis": {
            "description": "AI analysis of your documents and messages",
            "legal_basis": "consent",
            "opt_out_allowed": True,
            "default": False
        },
        "ai_model_training": {
            "description": "Using your interactions to improve our AI models",
            "legal_basis": "consent",
            "opt_out_allowed": True,
            "default": False
        },
        "ai_third_party": {
            "description": "Processing your data with third-party AI providers",
            "legal_basis": "consent",
            "opt_out_allowed": True,
            "default": False,
            "requires": ["ai_content_analysis"]  # Can't use third-party without content analysis consent
        }
    }
    
    def check_consent(self, user_id: str, category: str, feature: str) -> bool:
        consent_record = self.consent_store.get(user_id, category)
        
        if consent_record is None:
            # No record — check if legitimate interest applies
            cat_config = self.CONSENT_CATEGORIES[category]
            if cat_config["legal_basis"] == "legitimate_interest":
                return True  # Allowed unless opted out
            return False  # Requires explicit consent
        
        if not consent_record.is_valid():
            # Consent expired or withdrawn
            return False
        
        # Check feature-level granularity
        if feature and not consent_record.covers_feature(feature):
            return False
        
        return True
    
    def enforce_in_pipeline(self, user_id: str, request: dict) -> dict:
        """Middleware that modifies request based on consent"""
        
        if not self.check_consent(user_id, "ai_content_analysis"):
            # Strip user content from context — AI can only use metadata
            request["context"] = self.strip_content(request.get("context", ""))
        
        if not self.check_consent(user_id, "ai_personalization"):
            # Don't include user history in prompt
            request["user_history"] = None
            request["preferences"] = None
        
        if not self.check_consent(user_id, "ai_third_party"):
            # Force on-premise/first-party model only
            request["model_constraint"] = "first_party_only"
        
        if not self.check_consent(user_id, "ai_model_training"):
            # Tag this interaction as non-trainable
            request["metadata"]["training_excluded"] = True
        
        return request
```

---

## Synthetic Data for Evaluation

### Generating Privacy-Safe Eval Datasets

```python
class SyntheticEvalGenerator:
    """
    Generate evaluation datasets that preserve statistical properties
    of production data without containing real PII.
    
    Techniques:
    1. LLM-based synthesis (generate similar but fake examples)
    2. Differential privacy aggregation
    3. Template-based generation with faker
    4. Statistical distribution matching
    """
    
    def generate_from_production_patterns(self, prod_dataset: list, n_synthetic: int) -> list:
        """
        Step 1: Analyze production data patterns (without storing PII)
        Step 2: Generate synthetic data matching those patterns
        """
        
        # Analyze patterns (aggregate statistics only)
        patterns = self.analyze_patterns(prod_dataset)
        # patterns = {
        #   "avg_query_length": 47,
        #   "topic_distribution": {"finance": 0.3, "health": 0.2, ...},
        #   "complexity_distribution": {"simple": 0.4, "medium": 0.35, "complex": 0.25},
        #   "entity_types_present": ["PERSON": 0.6, "ORG": 0.4, "MONEY": 0.3],
        #   "query_templates": [...extracted templates with PII removed...]
        # }
        
        # Generate synthetic examples using LLM
        synthetic = []
        for i in range(n_synthetic):
            topic = self.sample_from_distribution(patterns["topic_distribution"])
            complexity = self.sample_from_distribution(patterns["complexity_distribution"])
            
            example = self.llm.generate(
                f"""Generate a realistic {complexity} user query about {topic}.
                Include realistic but FAKE: names, account numbers, dates, amounts.
                The query should be approximately {patterns['avg_query_length']} words.
                
                Also generate the expected correct answer.
                
                Format: {{"query": "...", "expected_answer": "...", "metadata": {{...}}}}"""
            )
            
            synthetic.append(json.loads(example))
        
        # Validate: ensure no production PII leaked into synthetic data
        self.validate_no_pii_leakage(synthetic, prod_dataset)
        
        return synthetic
    
    def validate_no_pii_leakage(self, synthetic: list, production: list):
        """Verify synthetic data doesn't accidentally contain real PII"""
        
        # Extract all PII from production data
        prod_pii = set()
        for item in production:
            entities = self.pii_detector.detect(item["query"])
            for entity in entities:
                prod_pii.add(entity["value"].lower())
        
        # Check synthetic data doesn't contain any production PII
        for item in synthetic:
            text = json.dumps(item).lower()
            for pii_value in prod_pii:
                if len(pii_value) > 3 and pii_value in text:  # Skip very short matches
                    raise PIILeakageError(
                        f"Synthetic data contains production PII: '{pii_value}'"
                    )
```

### Pitfalls of Synthetic Data

| Pitfall | Description | Mitigation |
|---------|-------------|------------|
| Memorization | LLM may reproduce training data verbatim | Cross-check against prod data |
| Distribution shift | Synthetic may not match real complexity | Statistical validation |
| Edge cases missed | Rare but important patterns under-represented | Explicit edge case generation |
| False confidence | High eval scores on synthetic ≠ production performance | Always validate sample on real data |
| Name collisions | Fake "John Smith" matches a real user | Use clearly fictional names |

---

## Vendor Data Processing Agreements: Comparison

### What Happens to Your Data

| Aspect | OpenAI API | Anthropic API | Azure OpenAI | Google Vertex AI |
|--------|-----------|---------------|-------------|-----------------|
| Training on your data | No (since Mar 2023) | No | No | No (by default) |
| Data retention | 30 days (abuse monitoring) | 30 days | 0 days (opt-out available) | 30 days |
| Zero data retention option | Yes (via API flag) | Enterprise only | Yes (standard) | Yes |
| Geographic processing | US (default) | US | Your chosen region | Your chosen region |
| Sub-processors | Listed publicly | Listed publicly | Microsoft only | Google only |
| SOC 2 Type II | Yes | Yes | Yes | Yes |
| HIPAA BAA available | Enterprise only | Enterprise | Yes | Yes |
| EU data processing | Via DPA | Via DPA | EU regions available | EU regions available |
| Right to audit | Limited | Limited | Yes (enterprise) | Yes (enterprise) |
| Breach notification | 72 hours | 72 hours | 72 hours | 72 hours |

### Key DPA Clauses to Verify

```python
DPA_CHECKLIST = {
    "data_use_restriction": {
        "question": "Can the vendor use my data for ANY purpose beyond providing the service?",
        "acceptable": "No — data used solely to provide and maintain the service",
        "red_flag": "Vendor retains rights to use data for 'service improvement'"
    },
    "sub_processor_control": {
        "question": "Can the vendor engage new sub-processors without my consent?",
        "acceptable": "Prior written notice with right to object",
        "red_flag": "Vendor can add sub-processors with only website notification"
    },
    "data_deletion": {
        "question": "What happens to my data after contract termination?",
        "acceptable": "Deleted within 30 days, certification provided",
        "red_flag": "Retained for undefined 'reasonable period'"
    },
    "breach_scope": {
        "question": "Does breach notification cover unauthorized access to prompts/responses?",
        "acceptable": "Yes — any unauthorized access to customer data",
        "red_flag": "Only covers 'confirmed exfiltration of personal data'"
    },
    "model_isolation": {
        "question": "Is my data isolated from other customers during processing?",
        "acceptable": "Logical isolation with encryption at rest and in transit",
        "red_flag": "Shared processing without clear isolation guarantees"
    }
}
```

---

## Privacy Impact Assessment: Step-by-Step

### Scenario: New AI Feature — "Smart Reply Suggestions"

An email platform wants to add AI-generated reply suggestions. The PIA process:

```
┌─────────────────────────────────────────────────────────────┐
│           Privacy Impact Assessment Framework                 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Step 1: Data Flow Mapping                                   │
│  Step 2: Necessity & Proportionality                         │
│  Step 3: Risk Identification                                 │
│  Step 4: Risk Scoring                                        │
│  Step 5: Mitigation Measures                                 │
│  Step 6: Residual Risk Assessment                            │
│  Step 7: Decision & Documentation                            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Step 1: Data Flow Mapping

```yaml
feature: smart_reply_suggestions
data_flows:
  - source: user_inbox
    data_categories:
      - email_body (personal correspondence)
      - sender_info (name, email)
      - thread_context (previous replies)
      - attachments_metadata (not content)
    processing: 
      - sent to LLM for suggestion generation
    destination: displayed to user (not stored)
    retention: none (real-time only)
    
  - source: user_interaction
    data_categories:
      - which suggestions accepted/rejected
      - modification patterns
    processing:
      - aggregated for quality metrics
    destination: analytics system
    retention: 90 days (anonymized after 30)
```

### Step 2: Risk Scoring Matrix

```python
RISK_MATRIX = {
    "data_breach_exposure": {
        "likelihood": "medium",      # LLM provider could be breached
        "impact": "high",            # Email content is highly sensitive
        "inherent_risk": "HIGH",
        "mitigations": [
            "Zero data retention with provider",
            "PII redaction before sending",
            "End-to-end encryption in transit"
        ],
        "residual_risk": "MEDIUM"
    },
    "unauthorized_profiling": {
        "likelihood": "low",         # We don't store suggestions
        "impact": "high",            # Could reveal personal info
        "inherent_risk": "MEDIUM",
        "mitigations": [
            "No suggestion storage",
            "No feedback loop to model training",
            "User can disable feature"
        ],
        "residual_risk": "LOW"
    },
    "model_memorization": {
        "likelihood": "low",         # Using API, not fine-tuning
        "impact": "high",            # Could leak email content
        "inherent_risk": "MEDIUM",
        "mitigations": [
            "Use zero-retention API endpoint",
            "Verify vendor DPA prohibits training",
            "Regular audits of vendor compliance"
        ],
        "residual_risk": "LOW"
    },
    "function_creep": {
        "likelihood": "medium",      # Tempting to use data for more
        "impact": "medium",          # Could expand beyond consent
        "inherent_risk": "MEDIUM",
        "mitigations": [
            "Strict purpose limitation in code",
            "Technical controls preventing repurposing",
            "Quarterly purpose review"
        ],
        "residual_risk": "LOW"
    },
    "consent_validity": {
        "likelihood": "medium",      # Users may not understand implications
        "impact": "medium",
        "inherent_risk": "MEDIUM",
        "mitigations": [
            "Clear, plain-language consent dialog",
            "Granular opt-in (not bundled)",
            "Easy to disable at any time",
            "No service degradation if disabled"
        ],
        "residual_risk": "LOW"
    }
}
```

### Step 3: Decision

```yaml
pia_decision:
  overall_residual_risk: MEDIUM
  recommendation: APPROVE_WITH_CONDITIONS
  conditions:
    - Must implement PII redaction pipeline (Layer 1-3)
    - Must use zero-retention API endpoint
    - Must implement granular opt-in consent
    - Must conduct penetration test before launch
    - Must implement output monitoring for PII leakage
    - Review after 6 months of operation
  
  dpo_sign_off_required: true  # Because processing personal email content
  
  review_schedule:
    - 30_days_post_launch: automated_monitoring_review
    - 90_days_post_launch: full_pia_refresh
    - annually: comprehensive_review
```

---

## Data Classification for AI Systems

### Classification Levels and Processing Rules

```python
class DataClassificationEngine:
    """
    Four-tier classification system for AI data processing.
    Each level has specific rules about what AI operations are permitted.
    """
    
    CLASSIFICATION_LEVELS = {
        "PUBLIC": {
            "level": 0,
            "description": "Publicly available information",
            "examples": ["product descriptions", "public documentation", "marketing content"],
            "ai_rules": {
                "can_send_to_any_llm": True,
                "can_use_for_training": True,
                "can_store_in_logs": True,
                "can_cache": True,
                "encryption_required": False,
                "geographic_restriction": None
            }
        },
        "INTERNAL": {
            "level": 1,
            "description": "Internal business information",
            "examples": ["internal wikis", "meeting notes", "project plans"],
            "ai_rules": {
                "can_send_to_any_llm": False,
                "allowed_providers": ["azure_openai", "self_hosted"],
                "can_use_for_training": False,
                "can_store_in_logs": True,  # Internal logs only
                "can_cache": True,
                "encryption_required": True,
                "geographic_restriction": None,
                "retention_max_days": 90
            }
        },
        "CONFIDENTIAL": {
            "level": 2,
            "description": "Sensitive business or personal data",
            "examples": ["customer PII", "financial data", "employee records", "contracts"],
            "ai_rules": {
                "can_send_to_any_llm": False,
                "allowed_providers": ["azure_openai_with_dpa"],
                "can_use_for_training": False,
                "can_store_in_logs": False,  # Must redact before logging
                "can_cache": False,
                "encryption_required": True,
                "geographic_restriction": "same_region_as_data_subject",
                "pii_redaction_required": True,
                "retention_max_days": 30,
                "access_logging_required": True
            }
        },
        "RESTRICTED": {
            "level": 3,
            "description": "Highly sensitive data with legal/regulatory constraints",
            "examples": ["health records (HIPAA)", "payment card data (PCI)", "classified info"],
            "ai_rules": {
                "can_send_to_any_llm": False,
                "allowed_providers": ["self_hosted_only"],
                "can_use_for_training": False,
                "can_store_in_logs": False,
                "can_cache": False,
                "encryption_required": True,
                "geographic_restriction": "specific_approved_locations",
                "pii_redaction_required": True,
                "requires_approval": True,
                "retention_max_days": 0,  # Process and discard immediately
                "access_logging_required": True,
                "audit_trail_immutable": True,
                "human_review_required": True
            }
        }
    }
    
    def classify_and_enforce(self, data: str, context: dict) -> dict:
        """Classify data and return processing constraints"""
        
        # Auto-classification using content analysis
        classification = self.classify(data, context)
        rules = self.CLASSIFICATION_LEVELS[classification]["ai_rules"]
        
        return {
            "classification": classification,
            "rules": rules,
            "allowed_operations": self.get_allowed_operations(rules),
            "required_controls": self.get_required_controls(rules)
        }
    
    def classify(self, data: str, context: dict) -> str:
        """Multi-signal classification"""
        signals = []
        
        # Signal 1: Source metadata
        if context.get("source_system") in ["hr_system", "payroll"]:
            signals.append("CONFIDENTIAL")
        if context.get("source_system") in ["ehr", "pci_vault"]:
            signals.append("RESTRICTED")
        
        # Signal 2: Content analysis
        pii_detected = self.pii_detector.detect(data)
        if any(p["type"] in ["SSN", "CREDIT_CARD", "HEALTH_RECORD"] for p in pii_detected):
            signals.append("RESTRICTED")
        elif any(p["type"] in ["PERSON", "EMAIL", "PHONE", "ADDRESS"] for p in pii_detected):
            signals.append("CONFIDENTIAL")
        
        # Signal 3: Document labels/markings
        if "CONFIDENTIAL" in data.upper()[:500]:
            signals.append("CONFIDENTIAL")
        
        # Signal 4: Data catalog metadata
        if context.get("catalog_classification"):
            signals.append(context["catalog_classification"])
        
        # Take the HIGHEST classification from all signals
        if not signals:
            return "INTERNAL"  # Default — never assume PUBLIC
        
        return max(signals, key=lambda s: self.CLASSIFICATION_LEVELS[s]["level"])
    
    def enforce_at_gateway(self, request: dict, data_classification: str) -> dict:
        """API gateway enforcement of classification rules"""
        rules = self.CLASSIFICATION_LEVELS[data_classification]["ai_rules"]
        
        # Check provider allowlist
        requested_provider = request.get("model_provider")
        if "allowed_providers" in rules:
            if requested_provider not in rules["allowed_providers"]:
                raise PolicyViolation(
                    f"Data classified as {data_classification} cannot be sent to "
                    f"{requested_provider}. Allowed: {rules['allowed_providers']}"
                )
        
        # Enforce PII redaction
        if rules.get("pii_redaction_required"):
            request["content"] = self.pii_redactor.redact(request["content"])
        
        # Enforce geographic restriction
        if rules.get("geographic_restriction"):
            endpoint_region = self.get_endpoint_region(request["endpoint"])
            required_region = self.resolve_region_constraint(
                rules["geographic_restriction"], request.get("data_subject_region")
            )
            if endpoint_region != required_region:
                raise PolicyViolation(
                    f"Data must be processed in {required_region}, "
                    f"but endpoint is in {endpoint_region}"
                )
        
        # Enforce caching rules
        if not rules.get("can_cache", True):
            request["headers"]["Cache-Control"] = "no-store"
            request["headers"]["X-No-Cache"] = "true"
        
        # Enforce logging rules
        if not rules.get("can_store_in_logs", True):
            request["metadata"]["suppress_logging"] = True
        
        # Require approval for restricted data
        if rules.get("requires_approval"):
            approval = self.get_approval(request, data_classification)
            if not approval.is_valid():
                raise PolicyViolation("Processing RESTRICTED data requires prior approval")
        
        return request
```

### Real Enforcement Example

```
User uploads a document to AI assistant:

1. Document arrives at API gateway
2. Classification engine scans first 1000 chars + metadata
3. Detects: "Patient: Jane Doe, MRN: 12345, Diagnosis: Type 2 Diabetes"
4. Classification: RESTRICTED (health data)
5. Enforcement:
   - Block: Cannot send to OpenAI API (third-party)
   - Allow: Self-hosted Llama 3 on-premises
   - Redact: "Patient: [PERSON_1], MRN: [MRN_1], Diagnosis: Type 2 Diabetes"
   - Route: Process in EU-West region (patient's country)
   - Log: Record access with justification, no content in logs
   - Retain: Response not cached, ephemeral processing only
6. Response returned to user
7. Audit entry created (who, when, why, what classification, what controls applied)
```

---

## Summary: Privacy Engineering Checklist for AI Systems

```
□ Data classification scheme defined and automated
□ PII detection pipeline (regex + NER + LLM) deployed at ingestion
□ Consent management system with granular per-feature controls
□ Right-to-delete pipeline covering ALL data stores (12+ locations)
□ Data residency routing enforced at infrastructure level
□ Vendor DPAs reviewed for AI-specific clauses
□ Privacy Impact Assessment completed for each AI feature
□ Synthetic data generation for safe evaluation
□ Access control on RAG retrieval (need-to-know)
□ Output monitoring for PII leakage in responses
□ Audit trail for all AI data access (immutable)
□ Retention policies enforced automatically
□ Breach notification procedures tested
□ Regular privacy audits scheduled
□ User transparency (what AI does with their data)
```
