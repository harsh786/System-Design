# Security & Authorization for AI Systems - Staff Architect Interview

## Question 66: Zero-Trust Architecture for LLM Applications
**Difficulty: Staff Level | Topic: Security Architecture | Asked at: Microsoft, Google, Amazon**

Design a zero-trust security architecture for an enterprise LLM application that accesses sensitive corporate data through RAG. The system must enforce principle of least privilege at every layer.

### Expected Answer:

**Zero-Trust LLM Security Architecture:**

1. **Trust Boundaries:**
   ```
   ┌─────────────────────────────────────────────────────────┐
   │ Trust Boundary 1: User Authentication                    │
   │ (Identity verification, MFA, device posture)             │
   ├─────────────────────────────────────────────────────────┤
   │ Trust Boundary 2: API Gateway                            │
   │ (Rate limiting, token validation, request signing)       │
   ├─────────────────────────────────────────────────────────┤
   │ Trust Boundary 3: RAG Retrieval                          │
   │ (Document-level ACL enforcement, data classification)    │
   ├─────────────────────────────────────────────────────────┤
   │ Trust Boundary 4: LLM Inference                          │
   │ (Input sanitization, output filtering, audit logging)    │
   ├─────────────────────────────────────────────────────────┤
   │ Trust Boundary 5: Response Delivery                      │
   │ (DLP scanning, PII redaction, classification marking)    │
   └─────────────────────────────────────────────────────────┘
   ```

2. **Document-Level Access Control:**
   ```python
   class SecureRAGRetriever:
       async def retrieve(self, query: str, user_context: AuthContext) -> List[Document]:
           # Step 1: Determine user's permissions
           user_permissions = await self.get_permissions(user_context)
           # {departments: ['engineering'], clearance: 'confidential', projects: ['alpha']}
           
           # Step 2: Build security filter
           security_filter = self.build_acl_filter(user_permissions)
           # Only retrieve documents the user is authorized to see
           
           # Step 3: Vector search WITH security filter
           results = await self.vector_db.search(
               query_embedding=self.embed(query),
               filter=security_filter,
               top_k=10
           )
           
           # Step 4: Post-retrieval verification (defense in depth)
           verified = []
           for doc in results:
               if await self.verify_access(user_context, doc.id):
                   verified.append(doc)
               else:
                   self.audit_log.warn(f"ACL bypass attempt: {user_context.user_id} → {doc.id}")
           
           return verified
       
       def build_acl_filter(self, permissions):
           return {
               "$and": [
                   {"classification": {"$lte": permissions.clearance_level}},
                   {"$or": [
                       {"department": {"$in": permissions.departments}},
                       {"visibility": "public"},
                       {"shared_with": permissions.user_id}
                   ]}
               ]
           }
   ```

3. **Request-Level Security:**
   ```python
   class SecureRequestPipeline:
       async def process(self, request: LLMRequest) -> LLMResponse:
           # Authentication
           identity = await self.verify_identity(request.token)
           
           # Authorization (can this user use this feature?)
           await self.check_authorization(identity, request.feature)
           
           # Input validation (prevent injection)
           sanitized_input = self.sanitize_input(request.query)
           
           # Rate limiting (per user, per org, per feature)
           await self.rate_limiter.check(identity)
           
           # Audit trail (before processing)
           audit_id = self.audit_log.begin(identity, sanitized_input)
           
           # Process with security context
           response = await self.rag_pipeline.process(
               sanitized_input, 
               security_context=identity
           )
           
           # Output filtering (DLP, PII, classification)
           filtered_response = await self.output_filter(response, identity)
           
           # Complete audit trail
           self.audit_log.complete(audit_id, filtered_response)
           
           return filtered_response
   ```

4. **Data Classification Enforcement:**
   | Classification | Who Can Access | RAG Behavior | Output Handling |
   |---------------|---------------|--------------|-----------------|
   | Public | Anyone | No restrictions | No marking |
   | Internal | Employees | Filter by org | Mark "Internal" |
   | Confidential | Department | Filter by dept + role | Mark + DLP scan |
   | Restricted | Named individuals | Explicit ACL only | Encrypt + audit |
   | Top Secret | Special clearance | Separate index entirely | Air-gapped system |

5. **Key Principles:**
   - Never cache responses containing sensitive data
   - Encrypt all data in transit (mTLS between services) and at rest
   - Rotate all credentials automatically (no long-lived tokens)
   - Assume the LLM is an untrusted component (it may leak context)
   - Log everything, alert on anomalies (unusual access patterns)

---

## Question 67: RBAC/ABAC for RAG Systems
**Difficulty: Staff Level | Topic: Access Control | Asked at: Salesforce, Microsoft, ServiceNow**

Design a fine-grained access control system for a RAG platform where different users should see different subsets of the same document. For example, an HR document where managers see salary info but employees only see policy text.

### Expected Answer:

**Fine-Grained Access Control for RAG:**

1. **Chunk-Level Permissions:**
   ```python
   class ChunkLevelACL:
       def index_document(self, document, acl_policy):
           chunks = self.chunk_document(document)
           
           for chunk in chunks:
               # Determine chunk sensitivity
               sensitivity = self.classify_sensitivity(chunk.text)
               
               # Apply section-level ACL
               chunk_acl = self.resolve_acl(
                   document_acl=acl_policy,
                   section_type=chunk.section_type,
                   sensitivity=sensitivity,
                   entities=self.extract_entities(chunk.text)
               )
               
               # Store chunk with ACL metadata
               self.vector_db.upsert(
                   id=chunk.id,
                   vector=self.embed(chunk.text),
                   metadata={
                       'text': chunk.text,
                       'acl': chunk_acl.serialize(),
                       'classification': sensitivity.level,
                       'pii_types': sensitivity.pii_types,
                       'roles_required': chunk_acl.required_roles,
                       'departments': chunk_acl.departments
                   }
               )
   ```

2. **ABAC (Attribute-Based Access Control) Engine:**
   ```python
   class ABACEngine:
       def evaluate(self, subject: User, resource: Chunk, action: str) -> bool:
           """
           Policy example:
           - Subject.role == 'manager' AND Subject.department == Resource.department
             → ALLOW view salary information
           - Subject.role == 'employee'
             → ALLOW view policy text, DENY view salary/PII
           """
           policies = self.load_policies(resource.classification)
           
           for policy in policies:
               decision = policy.evaluate(
                   subject_attributes={
                       'role': subject.role,
                       'department': subject.department,
                       'clearance': subject.clearance_level,
                       'projects': subject.projects,
                       'location': subject.location
                   },
                   resource_attributes={
                       'classification': resource.classification,
                       'department': resource.department,
                       'pii_types': resource.pii_types,
                       'content_type': resource.content_type
                   },
                   environment={
                       'time': datetime.now(),
                       'device_trust': subject.device_posture,
                       'network': subject.network_zone
                   }
               )
               if decision == 'DENY':
                   return False
           
           return True  # Default allow if no deny policies match
   ```

3. **Dynamic Content Redaction:**
   ```python
   class ContentRedactor:
       def redact_for_user(self, chunk: Chunk, user: User) -> str:
           """Redact portions of a chunk based on user permissions."""
           text = chunk.text
           
           # Check each sensitive entity
           for entity in chunk.entities:
               if not self.user_can_see(user, entity):
                   if entity.type == 'salary':
                       text = text.replace(entity.value, '[SALARY REDACTED]')
                   elif entity.type == 'ssn':
                       text = text.replace(entity.value, '[PII REDACTED]')
                   elif entity.type == 'performance_rating':
                       text = text.replace(entity.value, '[CONFIDENTIAL]')
           
           return text
   ```

4. **Implementation Architecture:**
   ```
   User Query + Auth Token
        │
        ▼
   ┌──────────────┐
   │ AuthZ Engine │ ← Policies (OPA/Cedar)
   │              │ ← User Attributes (LDAP/Entra ID)
   └──────┬───────┘
          │ (ACL Filter generated)
          ▼
   ┌──────────────┐
   │ Vector Search│ ← Filter: ACL metadata match
   │ + ACL Filter │
   └──────┬───────┘
          │ (Filtered results)
          ▼
   ┌──────────────┐
   │ Redaction    │ ← Per-entity permissions
   │ Engine       │
   └──────┬───────┘
          │ (Safe content)
          ▼
   ┌──────────────┐
   │ LLM Generate │ ← Only sees authorized content
   └──────────────┘
   ```

5. **Performance Optimization:**
   - Pre-compute ACL filters at session start (cache for session duration)
   - Use bitmap indexes in vector DB for fast ACL filtering
   - Batch permission checks (don't call AuthZ per chunk)
   - Denormalize permissions into vector DB metadata (avoid joins)
   - Trade-off: Slightly stale permissions (5-min cache) for 10x better latency

---

## Question 68: API Security and Rate Limiting for AI Services
**Difficulty: Staff Level | Topic: API Security | Asked at: OpenAI, Anthropic, Amazon**

Design the API security and rate limiting system for a public-facing AI API (like OpenAI's API). Consider abuse prevention, DDoS protection, token-based billing, and fair usage enforcement across millions of API keys.

### Expected Answer:

**AI API Security & Rate Limiting Architecture:**

1. **Multi-Layer Rate Limiting:**
   ```
   Layer 1: Edge/CDN (Cloudflare/AWS Shield)
   - IP-based rate limiting: 1000 req/s per IP
   - Geographic blocking for sanctioned regions
   - Bot detection (fingerprinting, CAPTCHA challenges)
   
   Layer 2: API Gateway (Kong/Envoy)
   - API key validation
   - Per-key rate limits (RPM, TPM)
   - Request size limits (max input tokens)
   - Concurrent request limits
   
   Layer 3: Application
   - Per-model rate limits
   - Token budget enforcement (daily/monthly)
   - Abuse pattern detection
   - Cost-based throttling
   ```

2. **Token-Based Rate Limiting:**
   ```python
   class TokenBudgetLimiter:
       """Rate limit based on token consumption, not just request count."""
       
       async def check_and_deduct(self, api_key: str, request: APIRequest) -> Decision:
           # Estimate tokens for this request
           estimated_tokens = self.estimate_tokens(request)
           # Input tokens + estimated output tokens
           
           # Check budget
           account = await self.get_account(api_key)
           
           # Multiple limits checked simultaneously
           checks = {
               'rpm': self.check_rpm(account),          # Requests per minute
               'tpm': self.check_tpm(account, estimated_tokens),  # Tokens per minute
               'daily_budget': self.check_daily(account, estimated_tokens),
               'monthly_budget': self.check_monthly(account, estimated_tokens),
               'concurrent': self.check_concurrent(account),
           }
           
           for limit_name, result in checks.items():
               if not result.allowed:
                   return Decision(
                       allowed=False,
                       retry_after=result.retry_after,
                       limit_name=limit_name,
                       headers={
                           'X-RateLimit-Limit': result.limit,
                           'X-RateLimit-Remaining': result.remaining,
                           'X-RateLimit-Reset': result.reset_time
                       }
                   )
           
           # Reserve tokens (deduct from budget)
           await self.reserve_tokens(account, estimated_tokens)
           return Decision(allowed=True)
   ```

3. **Sliding Window Rate Limiting (Redis-based):**
   ```python
   class SlidingWindowLimiter:
       """Precise sliding window using Redis sorted sets."""
       
       async def is_allowed(self, key: str, limit: int, window_seconds: int) -> bool:
           now = time.time()
           window_start = now - window_seconds
           
           pipe = self.redis.pipeline()
           # Remove entries outside window
           pipe.zremrangebyscore(key, 0, window_start)
           # Count entries in window
           pipe.zcard(key)
           # Add current request
           pipe.zadd(key, {str(now): now})
           # Set expiry
           pipe.expire(key, window_seconds)
           
           results = await pipe.execute()
           current_count = results[1]
           
           return current_count < limit
   ```

4. **Abuse Detection Patterns:**
   | Pattern | Detection | Response |
   |---------|-----------|----------|
   | Prompt injection probing | Regex + classifier on inputs | Warn → throttle → ban |
   | Data exfiltration attempts | Output analysis for PII/code patterns | Block + alert |
   | Model extraction | Systematic querying patterns | Rate limit → captcha |
   | Credential stuffing | Failed auth attempts spike | Lockout + notify |
   | Token farming | Many keys from same payment/IP | Verify identity |
   | Free tier abuse | Multiple accounts, same behavior | Link accounts, enforce limits |

5. **Fair Queuing Under Load:**
   ```python
   class FairScheduler:
       """When system is overloaded, ensure fair distribution across customers."""
       
       def schedule(self, request, system_load):
           if system_load < 0.7:
               return Priority.NORMAL  # No throttling needed
           
           # Weighted fair queuing based on tier
           tier_weights = {'free': 1, 'pro': 5, 'enterprise': 20}
           customer_weight = tier_weights[request.tier]
           
           # Customers who've used less of their share get priority
           usage_ratio = request.customer.current_usage / request.customer.limit
           priority_score = customer_weight * (1 - usage_ratio)
           
           if system_load > 0.95:
               # Shed load: reject lowest priority requests
               if priority_score < self.shed_threshold:
                   return Priority.REJECT  # 503 with retry-after
           
           return Priority(score=priority_score)
   ```

---

## Question 69: Data Privacy in AI Systems (GDPR/CCPA)
**Difficulty: Staff Level | Topic: Compliance | Asked at: Microsoft, Google, Salesforce**

Design a privacy-preserving AI system that complies with GDPR (right to erasure, data minimization, purpose limitation) while maintaining a functional RAG system. How do you handle "right to be forgotten" when data is embedded in vector representations?

### Expected Answer:

**GDPR-Compliant RAG Architecture:**

1. **The Embedding Problem:**
   - Embeddings are derived from personal data
   - Inverting embeddings to recover text is increasingly possible
   - Deleting source document ≠ deleting information from embedding
   - Must delete: source document + embedding + cached results + training contributions

2. **Right to Erasure Implementation:**
   ```python
   class GDPRCompliantRAG:
       async def handle_erasure_request(self, data_subject_id: str):
           """Complete erasure within 72 hours (GDPR: 30 days, we target faster)."""
           
           # Step 1: Find all data associated with this subject
           affected_data = await self.data_registry.find_by_subject(data_subject_id)
           # Returns: documents, embeddings, cache entries, audit logs
           
           # Step 2: Delete from all stores
           deletion_tasks = []
           
           # Delete source documents
           for doc in affected_data.documents:
               deletion_tasks.append(self.doc_store.delete(doc.id))
           
           # Delete embeddings from vector DB
           for embedding_id in affected_data.embedding_ids:
               deletion_tasks.append(self.vector_db.delete(embedding_id))
           
           # Invalidate cached responses mentioning this subject
           for cache_key in affected_data.cache_entries:
               deletion_tasks.append(self.cache.delete(cache_key))
           
           # Delete from search logs
           deletion_tasks.append(
               self.search_logs.delete_by_subject(data_subject_id)
           )
           
           await asyncio.gather(*deletion_tasks)
           
           # Step 3: Verify deletion
           verification = await self.verify_erasure(data_subject_id)
           
           # Step 4: Log completion (meta-log, no personal data)
           self.compliance_log.record_erasure(
               request_id=request.id,
               completed_at=datetime.now(),
               data_categories_erased=affected_data.categories,
               verification_status=verification.status
           )
           
           return ErasureConfirmation(status='completed', verification=verification)
   ```

3. **Data Minimization by Design:**
   ```python
   class PrivacyAwareIndexer:
       def index_document(self, document):
           # Principle: Only embed what's necessary for retrieval
           
           # Step 1: Strip PII before embedding
           anonymized = self.anonymize(document)
           
           # Step 2: Embed anonymized version (for search)
           embedding = self.embed(anonymized.text)
           
           # Step 3: Store PII separately with strict access controls
           pii_store_id = self.pii_vault.store(
               document.pii_entities,
               retention_days=365,  # Auto-delete after retention period
               purpose='customer_support',  # Purpose limitation
               consent_id=document.consent_reference
           )
           
           # Step 4: Index with reference to PII (not PII itself)
           self.vector_db.upsert(
               id=document.id,
               vector=embedding,
               metadata={
                   'text': anonymized.text,  # No PII in vector DB
                   'pii_reference': pii_store_id,  # Separate secure store
                   'data_subject_id': document.subject_id,  # For erasure lookup
                   'consent_scope': document.consent_scope,
                   'retention_expiry': document.retention_date
               }
           )
   ```

4. **Purpose Limitation Enforcement:**
   ```python
   class PurposeLimitationEngine:
       def check_purpose(self, query_context: QueryContext, document: Document) -> bool:
           """Ensure document is only used for its consented purpose."""
           
           # What purpose is this query serving?
           query_purpose = query_context.declared_purpose  # e.g., 'customer_support'
           
           # What purposes was this data collected for?
           allowed_purposes = document.consent_scope  # e.g., ['customer_support', 'product_improvement']
           
           if query_purpose not in allowed_purposes:
               self.audit_log.log_purpose_violation(query_context, document)
               return False
           
           return True
   ```

5. **Technical Challenges & Solutions:**
   | Challenge | Solution |
   |-----------|----------|
   | Embedding inversion attacks | Use dimensionality reduction, add noise |
   | Residual data in model weights | Don't fine-tune on personal data; use RAG only |
   | Cached responses contain PII | TTL-based cache with subject-id tagging |
   | Audit logs themselves contain PII | Pseudonymize logs, separate retention |
   | Cross-border data transfer | Region-locked vector indices |
   | Data lineage tracking | Every vector has provenance metadata |

---

## Question 70: Model Supply Chain Security
**Difficulty: Staff Level | Topic: Supply Chain | Asked at: Google, Microsoft, NVIDIA**

You're deploying open-source LLMs (Llama, Mistral) and embedding models in production. Design a model supply chain security framework that prevents supply chain attacks (backdoored models, poisoned weights, malicious model cards).

### Expected Answer:

**Model Supply Chain Security Framework:**

1. **Threat Model:**
   | Threat | Vector | Impact |
   |--------|--------|--------|
   | Backdoored model | Compromised HuggingFace upload | Model produces harmful output on trigger |
   | Weight poisoning | MITM during download | Subtle quality degradation or data exfil |
   | Dependency attack | Malicious tokenizer/library | Code execution during model loading |
   | Model card fraud | Fake performance claims | Wrong model deployed for use case |
   | Training data poison | Compromised training set | Biased/harmful model behavior |

2. **Secure Model Acquisition Pipeline:**
   ```python
   class ModelSupplyChain:
       def acquire_model(self, model_id: str, source: str) -> VerifiedModel:
           # Step 1: Source verification
           if source not in self.trusted_sources:
               raise UntrustedSourceError(source)
           
           # Step 2: Download with integrity verification
           model_files = self.download_with_checksum(
               model_id, 
               expected_checksums=self.get_checksums_from_registry(model_id)
           )
           
           # Step 3: Signature verification (if available)
           if self.has_signature(model_id):
               self.verify_signature(model_files, self.get_public_key(model_id))
           
           # Step 4: Vulnerability scanning
           scan_result = self.scan_for_vulnerabilities(model_files)
           # Check for: pickle exploits, arbitrary code in configs,
           # suspicious operations in model architecture
           
           if scan_result.has_critical:
               raise SecurityViolation(scan_result)
           
           # Step 5: Sandboxed testing
           test_results = self.sandboxed_evaluation(model_files)
           # Run in isolated container, monitor system calls,
           # check for network access attempts, file system writes
           
           # Step 6: Behavioral testing
           behavioral = self.behavioral_test(model_files, self.safety_test_suite)
           # Test for backdoor triggers, harmful outputs, data leakage
           
           # Step 7: Register in internal model registry
           return self.register_verified_model(
               model_files, 
               verification_report={
                   'checksums': model_files.checksums,
                   'scan_results': scan_result,
                   'behavioral_tests': behavioral,
                   'acquired_date': datetime.now(),
                   'source': source,
                   'verified_by': 'automated_pipeline'
               }
           )
   ```

3. **Internal Model Registry:**
   ```
   ┌─────────────────────────────────────────┐
   │  Internal Model Registry                 │
   ├─────────────────────────────────────────┤
   │  - Verified models only                  │
   │  - Immutable storage (content-addressed) │
   │  - Signed by security team               │
   │  - Version pinning (no auto-updates)     │
   │  - Dependency locking                    │
   │  - SBOM (Software Bill of Materials)     │
   │  - Continuous monitoring post-deployment │
   └─────────────────────────────────────────┘
   ```

4. **Runtime Security:**
   ```python
   class SecureModelRuntime:
       def load_model(self, model_id: str):
           # Only load from internal registry
           model_path = self.registry.get_verified_path(model_id)
           
           # Verify integrity before loading
           if not self.verify_checksums(model_path):
               raise TamperedModelError()
           
           # Load in sandboxed environment
           model = self.sandbox.load(
               model_path,
               allowed_ops=['inference'],  # No training, no file access
               network_access=False,
               max_memory='16GB'
           )
           
           # Continuous behavioral monitoring
           self.monitor.attach(model, checks=[
               'output_toxicity',
               'unexpected_patterns',
               'performance_degradation'
           ])
           
           return model
   ```

5. **Incident Response:**
   - Model vulnerability discovered → Immediate quarantine
   - Automated rollback to last-known-good version
   - Impact assessment: What queries were served by compromised model?
   - Notification: Users informed if outputs may have been affected
   - Post-mortem: How did compromised model enter pipeline?
