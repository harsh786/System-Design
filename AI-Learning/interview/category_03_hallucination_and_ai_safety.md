# AI Safety & Responsible AI Systems - Staff Architect Interview

## Question 46: Guardrails Architecture for Production LLMs
**Difficulty: Staff Level | Topic: AI Safety | Asked at: OpenAI, Anthropic, Google, Microsoft**

Design a comprehensive guardrails system for a production LLM that handles 1M requests/day. The system must prevent harmful outputs, detect prompt injection, enforce content policies, and operate with <50ms added latency. How do you balance safety with user experience?

### Expected Answer:

**Production Guardrails Architecture:**

1. **Multi-Layer Defense:**
   ```
   User Input
       │
       ▼
   ┌─────────────────┐  <5ms
   │ Layer 1: Input   │  Blocklist, regex, rate limits
   │ Fast Filters     │  (Deterministic, zero false negatives for known patterns)
   └────────┬────────┘
            │
            ▼
   ┌─────────────────┐  <20ms
   │ Layer 2: Input   │  Classifier models (injection, toxicity, PII)
   │ Classifiers      │  (ML-based, catches novel attacks)
   └────────┬────────┘
            │
            ▼
   ┌─────────────────┐  Model generation time
   │ Layer 3: System  │  System prompt hardening
   │ Prompt Defense   │  (Instructions the model always follows)
   └────────┬────────┘
            │
            ▼
   ┌─────────────────┐  <15ms
   │ Layer 4: Output  │  Toxicity, factuality, policy compliance
   │ Validators       │  (Catches harmful completions)
   └────────┬────────┘
            │
            ▼
   ┌─────────────────┐  <5ms
   │ Layer 5: Output  │  PII redaction, format validation
   │ Post-processing  │  (Deterministic cleanup)
   └────────┬────────┘
            │
            ▼
       Response to User
   ```

2. **Prompt Injection Detection:**
   ```python
   class PromptInjectionDetector:
       """
       Detect attempts to override system instructions.
       Types: Direct injection, indirect injection (in retrieved content),
              jailbreaks, role-play exploits.
       """
       
       def __init__(self):
           self.classifier = load_model('injection_detector_v3')  # Fine-tuned BERT
           self.heuristic_rules = self.load_rules()
           self.canary_tokens = self.generate_canaries()
       
       def detect(self, user_input: str, context: str = None) -> DetectionResult:
           signals = []
           
           # Heuristic checks (fast, catches known patterns)
           for rule in self.heuristic_rules:
               if rule.matches(user_input):
                   signals.append(Signal(rule.name, confidence=0.9))
           
           # ML classifier (catches novel attempts)
           injection_score = self.classifier.predict(user_input)
           if injection_score > 0.7:
               signals.append(Signal('ml_classifier', confidence=injection_score))
           
           # Indirect injection: Check retrieved context for instructions
           if context:
               context_score = self.classifier.predict(context)
               if context_score > 0.5:
                   signals.append(Signal('indirect_injection', confidence=context_score))
           
           # Canary token check (in output)
           # If output contains our hidden canary, system prompt was leaked
           
           return DetectionResult(
               is_injection=any(s.confidence > 0.8 for s in signals),
               signals=signals,
               recommended_action=self.get_action(signals)
           )
       
       def get_action(self, signals):
           max_confidence = max(s.confidence for s in signals) if signals else 0
           if max_confidence > 0.95:
               return 'block'  # Definitely an attack
           elif max_confidence > 0.8:
               return 'flag_and_sanitize'  # Likely attack, sanitize input
           elif max_confidence > 0.5:
               return 'monitor'  # Suspicious, log for review
           return 'allow'
   ```

3. **Output Safety Classifier:**
   ```python
   class OutputSafetyValidator:
       """Validate LLM outputs before returning to user."""
       
       POLICY_CATEGORIES = [
           'harmful_instructions',  # How to cause harm
           'hate_speech',           # Targeting protected groups
           'sexual_content',        # Inappropriate sexual content
           'violence',              # Graphic violence
           'self_harm',             # Encouraging self-harm
           'misinformation',        # Demonstrably false claims
           'privacy_violation',     # Exposing personal info
           'copyright',             # Verbatim copyrighted text
       ]
       
       def validate(self, response: str, context: dict) -> ValidationResult:
           violations = []
           
           # Fast check: Content classifiers (parallel)
           category_scores = self.multi_label_classifier.predict(response)
           for category, score in category_scores.items():
               threshold = self.get_threshold(category, context)
               if score > threshold:
                   violations.append(Violation(category, score))
           
           # PII detection
           pii_entities = self.pii_detector.find(response)
           if pii_entities:
               violations.append(Violation('pii_leak', entities=pii_entities))
           
           # Policy-specific checks
           if context.get('user_age') and context['user_age'] < 18:
               # Stricter thresholds for minors
               violations.extend(self.check_minor_safety(response))
           
           if violations:
               return ValidationResult(
                   safe=False,
                   violations=violations,
                   action=self.determine_action(violations),
                   sanitized_response=self.sanitize(response, violations)
               )
           
           return ValidationResult(safe=True)
       
       def determine_action(self, violations):
           severities = [v.severity for v in violations]
           if 'critical' in severities:
               return 'block_and_report'
           elif 'high' in severities:
               return 'replace_with_refusal'
           else:
               return 'redact_violations'
   ```

4. **Latency-Optimized Architecture:**
   ```python
   class LowLatencyGuardrails:
       """Achieve <50ms total guardrails overhead."""
       
       def __init__(self):
           # Tiered approach: fast checks first, expensive checks only if needed
           self.fast_checks = FastChecks()       # <5ms (regex, blocklist)
           self.medium_checks = MediumChecks()   # <20ms (small classifiers)
           self.slow_checks = SlowChecks()       # <50ms (large classifiers)
       
       async def check_input(self, input_text):
           # Fast checks (always run, synchronous)
           fast_result = self.fast_checks.run(input_text)
           if fast_result.blocked:
               return fast_result  # Block immediately
           
           # Medium checks (run in parallel with model generation start)
           # Key insight: Start LLM generation while safety checks run
           # If safety check fails, discard the generation
           medium_future = asyncio.create_task(
               self.medium_checks.run(input_text)
           )
           
           return fast_result, medium_future
       
       async def check_output(self, output_text):
           """Stream-aware output checking."""
           # Check output in chunks as it streams (don't wait for full response)
           buffer = ""
           for chunk in output_text.stream():
               buffer += chunk
               
               # Check every 50 tokens
               if self.token_count(buffer) % 50 == 0:
                   quick_check = self.fast_checks.run(buffer)
                   if quick_check.blocked:
                       return self.stop_generation(reason=quick_check.reason)
           
           # Full output check
           return await self.medium_checks.run(buffer)
   ```

5. **Safety Monitoring & Improvement Loop:**
   ```python
   class SafetyMonitor:
       """Continuous monitoring and improvement of guardrails."""
       
       def track_metrics(self):
           return {
               # Effectiveness
               'block_rate': self.blocked_requests / self.total_requests,
               'false_positive_rate': self.false_positives / self.total_blocks,
               'false_negative_rate': self.missed_violations / self.total_violations,
               
               # User experience impact
               'avg_added_latency_ms': self.avg_guardrail_latency,
               'user_complaint_rate': self.complaints_about_overblocking,
               
               # Attack patterns
               'injection_attempt_rate': self.injection_attempts / self.total_requests,
               'novel_attack_rate': self.novel_attacks_detected,
               
               # Coverage
               'categories_covered': len(self.active_classifiers),
               'last_model_update': self.classifier_last_updated,
           }
       
       def red_team_integration(self):
           """Continuously test guardrails with adversarial inputs."""
           # Automated red-teaming: Use LLM to generate attack prompts
           attack_prompts = self.attack_generator.generate(n=1000)
           
           for prompt in attack_prompts:
               result = self.guardrails.check_input(prompt)
               if not result.blocked:
                   # Guardrails missed an attack!
                   self.log_bypass(prompt, result)
                   self.add_to_training_data(prompt, label='attack')
           
           # Retrain classifiers with new attack patterns monthly
           if self.new_training_data_count > 500:
               self.retrain_classifiers()
   ```

---

## Question 47: Bias Detection and Mitigation in ML Systems
**Difficulty: Staff Level | Topic: Fairness & Ethics | Asked at: Google, Meta, Microsoft, LinkedIn**

Design a system that continuously monitors ML model outputs for bias across protected attributes (race, gender, age). How do you detect bias without collecting sensitive attributes? How do you mitigate detected bias without significantly impacting overall model performance?

### Expected Answer:

**Bias Detection & Mitigation System:**

1. **Bias Detection Without Explicit Attributes:**
   ```python
   class ProxyBiasDetector:
       """
       Challenge: We often can't/shouldn't collect protected attributes.
       Solution: Use proxy methods and aggregate analysis.
       """
       
       def detect_bias_via_proxies(self, predictions, user_features):
           # Method 1: Geographic proxy
           # Zip codes correlate with demographics
           geo_groups = self.cluster_by_geography(user_features)
           for group_name, group_preds in geo_groups.items():
               self.check_disparity(group_name, group_preds, predictions)
           
           # Method 2: Name-based inference (for audit only, never for decisions)
           # Research shows first names correlate with demographics
           # Use ONLY for aggregate bias measurement, never individual decisions
           
           # Method 3: Counterfactual testing
           # Change demographic indicators in input, check if output changes
           bias_scores = self.counterfactual_test(predictions)
           
           # Method 4: Embedding cluster analysis
           # Check if embedding space has demographic clusters with different outcomes
           clusters = self.cluster_embeddings(user_features)
           for cluster in clusters:
               outcome_rate = self.compute_outcome_rate(cluster, predictions)
               if self.is_outlier(outcome_rate):
                   self.flag_potential_bias(cluster)
       
       def counterfactual_test(self, model, test_cases):
           """Swap demographic indicators, measure output change."""
           results = []
           for case in test_cases:
               # Generate counterfactuals
               variants = self.generate_counterfactuals(case)
               # e.g., "John" → "Jamal", "Sarah" → "Lakisha"
               
               predictions = [model.predict(v) for v in variants]
               
               # Measure disparity
               max_diff = max(predictions) - min(predictions)
               if max_diff > self.threshold:
                   results.append(BiasInstance(
                       original=case,
                       variants=variants,
                       predictions=predictions,
                       disparity=max_diff
                   ))
           
           return results
   ```

2. **Fairness Metrics Framework:**
   ```python
   class FairnessMetrics:
       """Multiple fairness definitions - often in tension with each other."""
       
       def compute_all_metrics(self, predictions, labels, groups):
           return {
               # Demographic Parity: P(Y_hat=1|A=a) = P(Y_hat=1|A=b)
               'demographic_parity': self.demographic_parity_ratio(
                   predictions, groups
               ),
               
               # Equalized Odds: P(Y_hat=1|Y=y,A=a) = P(Y_hat=1|Y=y,A=b)
               'equalized_odds': self.equalized_odds_diff(
                   predictions, labels, groups
               ),
               
               # Calibration: P(Y=1|Y_hat=p,A=a) = p for all groups
               'calibration_error': self.group_calibration_error(
                   predictions, labels, groups
               ),
               
               # Equal Opportunity: P(Y_hat=1|Y=1,A=a) = P(Y_hat=1|Y=1,A=b)
               'equal_opportunity': self.equal_opportunity_diff(
                   predictions, labels, groups
               ),
               
               # Predictive Parity: P(Y=1|Y_hat=1,A=a) = P(Y=1|Y_hat=1,A=b)
               'predictive_parity': self.predictive_parity_ratio(
                   predictions, labels, groups
               ),
           }
       
       def demographic_parity_ratio(self, predictions, groups):
           """Ratio of positive prediction rates between groups."""
           rates = {}
           for group in groups.unique():
               group_preds = predictions[groups == group]
               rates[group] = (group_preds > 0.5).mean()
           
           min_rate = min(rates.values())
           max_rate = max(rates.values())
           
           # 4/5 rule: ratio should be > 0.8 (legal standard)
           return min_rate / max_rate if max_rate > 0 else 1.0
   ```

3. **Bias Mitigation Strategies:**
   ```python
   class BiasMitigator:
       """Three approaches: pre-processing, in-processing, post-processing."""
       
       # Pre-processing: Fix the data
       def rebalance_training_data(self, data, protected_attribute):
           """Ensure training data is balanced across groups."""
           groups = data.groupby(protected_attribute)
           min_size = groups.size().min()
           
           # Option A: Undersample majority groups
           balanced = groups.apply(lambda x: x.sample(min_size))
           
           # Option B: Oversample minority groups (with augmentation)
           # Option C: Re-weight samples inversely to group frequency
           
           return balanced
       
       # In-processing: Constrained optimization
       def train_with_fairness_constraint(self, model, data, constraint='dp'):
           """Add fairness penalty to loss function."""
           for batch in data:
               predictions = model(batch.features)
               
               # Standard loss
               task_loss = cross_entropy(predictions, batch.labels)
               
               # Fairness penalty
               if constraint == 'dp':
                   # Demographic parity: minimize group prediction rate difference
                   group_rates = []
                   for group in batch.groups.unique():
                       mask = batch.groups == group
                       group_rates.append(predictions[mask].mean())
                   fairness_loss = variance(group_rates)
               
               # Combined loss (lambda controls trade-off)
               total_loss = task_loss + self.lambda_fairness * fairness_loss
               total_loss.backward()
       
       # Post-processing: Adjust thresholds per group
       def calibrate_thresholds(self, model, val_data, target_metric='equal_opportunity'):
           """Find group-specific thresholds that satisfy fairness constraint."""
           best_thresholds = {}
           
           for group in val_data.groups.unique():
               group_data = val_data[val_data.groups == group]
               predictions = model.predict(group_data.features)
               
               # Find threshold that equalizes true positive rate across groups
               best_threshold = self.binary_search_threshold(
                   predictions, group_data.labels, target_tpr=self.target_tpr
               )
               best_thresholds[group] = best_threshold
           
           return best_thresholds
   ```

4. **Continuous Bias Monitoring Dashboard:**
   ```python
   class BiasMonitoringPipeline:
       """Production monitoring for bias regression."""
       
       def daily_bias_audit(self):
           # Sample today's predictions
           predictions = self.sample_predictions(n=100000)
           
           # Compute fairness metrics using proxy groups
           metrics = self.fairness_metrics.compute_all_metrics(
               predictions.scores,
               predictions.outcomes,  # Delayed feedback
               predictions.proxy_groups
           )
           
           # Compare to baseline
           baseline = self.get_baseline_metrics()
           
           for metric_name, value in metrics.items():
               # Alert if fairness degrades
               if value < baseline[metric_name] - self.tolerance:
                   self.alert(
                       f"Bias regression: {metric_name} = {value:.3f} "
                       f"(baseline: {baseline[metric_name]:.3f})"
                   )
               
               # Track trends
               self.time_series_store.append(metric_name, value, time.time())
           
           return metrics
       
       def intersectional_analysis(self, predictions, attributes):
           """Check bias at intersections (e.g., Black women, elderly disabled)."""
           # Single-attribute analysis may miss intersectional harm
           from itertools import combinations
           
           for attr_combo in combinations(attributes, 2):
               groups = self.create_intersectional_groups(predictions, attr_combo)
               for group, group_preds in groups.items():
                   metric = self.compute_outcome_rate(group_preds)
                   if self.is_disparate(metric, self.overall_rate):
                       self.flag_intersectional_bias(group, attr_combo, metric)
   ```

5. **Bias-Aware Model Selection:**
   ```python
   class FairnessAwareModelSelector:
       """Select models that optimize both performance AND fairness."""
       
       def pareto_optimal_selection(self, candidate_models):
           """Find models on the performance-fairness Pareto frontier."""
           model_scores = []
           
           for model in candidate_models:
               performance = self.evaluate_performance(model)  # AUC, F1, etc.
               fairness = self.evaluate_fairness(model)        # DP ratio, EO diff
               
               model_scores.append({
                   'model': model,
                   'performance': performance,
                   'fairness': fairness,
               })
           
           # Find Pareto frontier (no model dominates on both axes)
           pareto_front = self.compute_pareto_frontier(
               model_scores, 
               objectives=['performance', 'fairness'],
               directions=['maximize', 'maximize']
           )
           
           # Select model based on business constraints
           # e.g., "fairness must be > 0.8, maximize performance subject to that"
           selected = max(
               [m for m in pareto_front if m['fairness'] > 0.8],
               key=lambda m: m['performance']
           )
           
           return selected
   ```

---

## Question 48: Privacy-Preserving ML Systems
**Difficulty: Staff Level | Topic: Privacy Engineering | Asked at: Apple, Google, Meta, Microsoft**

Design an ML system that trains on user data while providing formal privacy guarantees. Compare differential privacy, federated learning, and secure multi-party computation. How do you balance privacy budget with model utility?

### Expected Answer:

**Privacy-Preserving ML Architecture:**

1. **Techniques Comparison:**
   | Technique | Privacy Guarantee | Utility Loss | Compute Cost | Use Case |
   |-----------|-------------------|--------------|--------------|----------|
   | Differential Privacy (DP) | Mathematical (ε-DP) | 5-15% accuracy | 2-3x training | Central training with privacy |
   | Federated Learning (FL) | Data doesn't leave device | 3-10% accuracy | 10-100x communication | Mobile/edge devices |
   | Secure MPC | Computational security | <1% accuracy | 100-1000x compute | Multi-party collaboration |
   | Homomorphic Encryption | Mathematical | <1% accuracy | 10000x compute | Inference on encrypted data |
   | DP + FL (combined) | Strongest practical | 10-20% accuracy | High | Apple/Google keyboard |

2. **Differential Privacy Implementation:**
   ```python
   class DPTrainer:
       """
       Differentially private SGD (DP-SGD).
       Guarantee: Adding/removing one training example changes
       output distribution by at most factor e^ε.
       """
       
       def __init__(self, model, epsilon=8.0, delta=1e-5, max_grad_norm=1.0):
           self.model = model
           self.target_epsilon = epsilon
           self.delta = delta
           self.max_grad_norm = max_grad_norm
           self.noise_multiplier = self.calibrate_noise()
           self.privacy_accountant = RDPAccountant()
       
       def training_step(self, batch):
           # Step 1: Compute per-sample gradients
           per_sample_grads = self.compute_per_sample_gradients(batch)
           
           # Step 2: Clip each sample's gradient (bound sensitivity)
           clipped_grads = []
           for grad in per_sample_grads:
               grad_norm = torch.norm(grad)
               clip_factor = min(1.0, self.max_grad_norm / grad_norm)
               clipped_grads.append(grad * clip_factor)
           
           # Step 3: Aggregate and add Gaussian noise
           summed_grads = sum(clipped_grads)
           noise = torch.randn_like(summed_grads) * (
               self.noise_multiplier * self.max_grad_norm
           )
           noisy_grads = (summed_grads + noise) / len(batch)
           
           # Step 4: Update model
           self.optimizer.step(noisy_grads)
           
           # Step 5: Track privacy budget spent
           self.privacy_accountant.step(
               noise_multiplier=self.noise_multiplier,
               sample_rate=len(batch) / self.dataset_size
           )
           
           current_epsilon = self.privacy_accountant.get_epsilon(self.delta)
           if current_epsilon >= self.target_epsilon:
               raise PrivacyBudgetExhausted(
                   f"Reached ε={current_epsilon:.2f}, stopping training"
               )
       
       def calibrate_noise(self):
           """Determine noise level needed to achieve target epsilon."""
           # Binary search for noise_multiplier that gives target epsilon
           # after expected number of training steps
           lo, hi = 0.1, 100.0
           for _ in range(100):
               mid = (lo + hi) / 2
               eps = self.estimate_epsilon(mid, self.expected_steps)
               if eps < self.target_epsilon:
                   hi = mid
               else:
                   lo = mid
           return hi
   ```

3. **Federated Learning System:**
   ```python
   class FederatedLearningServer:
       """
       Coordinate training across millions of devices.
       Key: Raw data never leaves the device.
       """
       
       def __init__(self, model_architecture):
           self.global_model = model_architecture()
           self.round_number = 0
       
       def run_round(self):
           """One round of federated averaging."""
           self.round_number += 1
           
           # Step 1: Select participating devices (random subset)
           selected_devices = self.select_devices(
               n=1000,  # Of millions available
               criteria={
                   'battery': '>50%',
                   'network': 'wifi',
                   'idle': True,
                   'data_freshness': '<24h'
               }
           )
           
           # Step 2: Send current model to devices
           model_update = self.global_model.state_dict()
           
           # Step 3: Devices train locally (parallel, on-device)
           local_updates = []
           for device in selected_devices:
               update = device.train_locally(
                   model=model_update,
                   epochs=5,  # Local epochs
                   batch_size=32
               )
               local_updates.append(update)
           
           # Step 4: Aggregate updates (Federated Averaging)
           aggregated = self.secure_aggregate(local_updates)
           
           # Step 5: Update global model
           self.global_model.load_state_dict(aggregated)
       
       def secure_aggregate(self, updates):
           """
           Secure aggregation: Server learns only the SUM of updates,
           not individual device contributions.
           """
           # Each device adds random mask (masks cancel in sum)
           # Server only sees: sum(updates) + sum(masks) = sum(updates)
           # Individual update[i] is hidden
           
           # Additional: Add DP noise to aggregated update
           aggregated = federated_average(updates)
           noise = gaussian_noise(std=self.dp_noise_std)
           return aggregated + noise
   ```

4. **Privacy Budget Management:**
   ```python
   class PrivacyBudgetManager:
       """
       Track and allocate privacy budget across multiple uses.
       Key: Privacy loss is CUMULATIVE (composition theorem).
       """
       
       def __init__(self, total_epsilon=10.0, total_delta=1e-5):
           self.total_epsilon = total_epsilon
           self.total_delta = total_delta
           self.spent_epsilon = 0.0
           self.allocations = []
       
       def request_budget(self, purpose: str, epsilon_needed: float) -> bool:
           """Request privacy budget for a specific computation."""
           remaining = self.total_epsilon - self.spent_epsilon
           
           if epsilon_needed > remaining:
               self.alert(f"Budget request denied: need {epsilon_needed}, "
                        f"have {remaining}")
               return False
           
           self.allocations.append({
               'purpose': purpose,
               'epsilon': epsilon_needed,
               'timestamp': time.time(),
               'approved_by': self.get_approver(epsilon_needed),
           })
           self.spent_epsilon += epsilon_needed
           
           return True
       
       def get_remaining_budget(self):
           return self.total_epsilon - self.spent_epsilon
       
       def optimize_budget_allocation(self):
           """
           Key insight: Not all queries need the same privacy.
           Allocate more budget to important/frequent queries.
           """
           priorities = {
               'model_training': 0.6,      # 60% of budget
               'analytics_dashboards': 0.2, # 20% of budget
               'ad_hoc_queries': 0.1,       # 10% of budget
               'reserve': 0.1,              # 10% buffer
           }
           return {k: v * self.total_epsilon for k, v in priorities.items()}
   ```

5. **Privacy vs Utility Trade-off Analysis:**
   ```python
   class PrivacyUtilityAnalyzer:
       """Empirically measure privacy-utility trade-off for a given task."""
       
       def sweep_privacy_levels(self, dataset, model_class):
           """Train models at different privacy levels, measure accuracy."""
           results = []
           
           for epsilon in [0.1, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, float('inf')]:
               if epsilon == float('inf'):
                   # Non-private baseline
                   model = self.train_standard(dataset, model_class)
               else:
                   model = self.train_dp(dataset, model_class, epsilon=epsilon)
               
               accuracy = self.evaluate(model)
               results.append({
                   'epsilon': epsilon,
                   'accuracy': accuracy,
                   'utility_loss': baseline_accuracy - accuracy,
               })
           
           # Find the "knee" - best privacy for acceptable utility loss
           knee_point = self.find_knee(results)
           # Typical finding: ε=4-8 gives <5% utility loss for most tasks
           
           return results, knee_point
       
       def recommend_privacy_level(self, data_sensitivity, model_criticality):
           """
           Recommendations:
           - Medical records: ε ≤ 1.0 (strong privacy, accept utility loss)
           - Financial data: ε ≤ 4.0 (moderate privacy)
           - Behavioral data: ε ≤ 8.0 (reasonable privacy)
           - Public data: No DP needed
           """
           if data_sensitivity == 'high' and model_criticality == 'low':
               return 1.0  # Prioritize privacy
           elif data_sensitivity == 'high' and model_criticality == 'high':
               return 4.0  # Balance
           else:
               return 8.0  # Prioritize utility
   ```

---

## Question 49: Model Monitoring and Observability
**Difficulty: Staff Level | Topic: MLOps | Asked at: Netflix, Uber, Airbnb, Google**

Design a comprehensive monitoring system for 200+ ML models in production. How do you detect silent model failures (model returns predictions but they're wrong)? How do you handle delayed ground truth labels? Design alerting that minimizes false alarms while catching real degradation.

### Expected Answer:

**ML Model Monitoring System:**

1. **Monitoring Architecture:**
   ```
   ┌─────────────────────────────────────────────────────┐
   │              ML Monitoring Platform                    │
   ├─────────────────────────────────────────────────────┤
   │ Layer 1: Infrastructure │ GPU util, memory, latency  │
   │ Layer 2: Data Quality   │ Schema, distribution, volume│
   │ Layer 3: Model Quality  │ Predictions, confidence    │
   │ Layer 4: Business Impact│ Revenue, engagement, errors│
   └────────────────────┬────────────────────────────────┘
                        │
              ┌─────────▼─────────┐
              │  Anomaly Detection │
              │  Engine            │
              └─────────┬─────────┘
                        │
              ┌─────────▼─────────┐
              │  Alert Router      │
              │  (Smart grouping,  │
              │   dedup, priority) │
              └───────────────────┘
   ```

2. **Silent Failure Detection (No Ground Truth):**
   ```python
   class SilentFailureDetector:
       """
       Challenge: Model returns confident predictions, but they're wrong.
       No immediate ground truth to validate against.
       Solution: Multiple proxy signals.
       """
       
       def detect(self, model_id):
           signals = {}
           
           # Signal 1: Prediction Distribution Shift
           current_dist = self.get_prediction_distribution(model_id, window='1h')
           baseline_dist = self.get_baseline_distribution(model_id)
           signals['prediction_drift'] = ks_test(current_dist, baseline_dist)
           
           # Signal 2: Confidence Calibration Drift
           # If model used to be 90% accurate at 0.9 confidence,
           # but now it's only 70% accurate at 0.9 confidence → problem
           signals['calibration_drift'] = self.check_calibration_stability(model_id)
           
           # Signal 3: Feature Distribution Shift (Input Drift)
           for feature in self.get_top_features(model_id):
               signals[f'input_drift_{feature}'] = self.check_feature_drift(
                   model_id, feature
               )
           
           # Signal 4: Downstream Impact Signals
           # If recommendation model is fine but click-rate drops → model may be bad
           signals['downstream_metric'] = self.check_downstream_metrics(model_id)
           
           # Signal 5: Cross-Model Consistency
           # If model A and model B usually agree but now diverge → one is broken
           signals['cross_model_agreement'] = self.check_model_agreement(model_id)
           
           # Signal 6: User Behavior Anomalies
           # If users start ignoring model suggestions more than usual
           signals['user_override_rate'] = self.check_user_overrides(model_id)
           
           # Aggregate signals
           failure_probability = self.aggregate_signals(signals)
           if failure_probability > 0.8:
               self.trigger_investigation(model_id, signals)
       
       def check_model_agreement(self, model_id):
           """Compare predictions with redundant/ensemble models."""
           primary_preds = self.get_recent_predictions(model_id)
           shadow_preds = self.get_shadow_model_predictions(model_id)
           
           agreement_rate = (primary_preds == shadow_preds).mean()
           baseline_agreement = self.get_baseline_agreement(model_id)
           
           if agreement_rate < baseline_agreement - 0.1:
               return AnomalySignal(severity='high', 
                   detail=f"Agreement dropped: {agreement_rate:.2%} vs {baseline_agreement:.2%}")
           return AnomalySignal(severity='none')
   ```

3. **Handling Delayed Ground Truth:**
   ```python
   class DelayedLabelMonitor:
       """
       Many ML tasks have delayed feedback:
       - Fraud: Days to weeks (chargebacks)
       - Ads: Hours (conversions)
       - Content: Days (user engagement metrics)
       - Credit risk: Months (loan defaults)
       """
       
       def __init__(self, model_id, label_delay):
           self.model_id = model_id
           self.label_delay = label_delay  # e.g., timedelta(days=30)
           self.prediction_buffer = TimeSeriesBuffer()
       
       def on_prediction(self, prediction_id, features, score, timestamp):
           """Buffer predictions until labels arrive."""
           self.prediction_buffer.store(prediction_id, {
               'features': features,
               'score': score,
               'timestamp': timestamp,
           })
       
       def on_label_arrival(self, prediction_id, label):
           """When ground truth finally arrives, compute metrics."""
           prediction = self.prediction_buffer.get(prediction_id)
           
           # Add to evaluation window
           self.evaluation_store.append(
               prediction['score'], label, prediction['timestamp']
           )
           
           # Compute metrics on the window that now has labels
           window_start = time.time() - self.label_delay - timedelta(days=7)
           window_end = time.time() - self.label_delay
           
           metrics = self.compute_window_metrics(window_start, window_end)
           self.report_metrics(metrics, window_end)
       
       def early_warning_proxy(self):
           """Don't wait for labels - use proxy metrics for early detection."""
           # Fast proxy signals (available immediately):
           proxies = {
               'prediction_confidence_mean': self.avg_confidence(window='1h'),
               'prediction_entropy': self.avg_entropy(window='1h'),
               'feature_drift_score': self.compute_drift(window='1h'),
               'prediction_distribution_shift': self.dist_shift(window='1h'),
           }
           
           # Compare to values from the period that NOW has labels
           # (we know those predictions were good/bad)
           labeled_period_proxies = self.get_proxy_values(
               period=f'{self.label_delay.days} days ago'
           )
           
           for proxy_name, current_value in proxies.items():
               historical_value = labeled_period_proxies[proxy_name]
               if abs(current_value - historical_value) > self.thresholds[proxy_name]:
                   self.early_warning(proxy_name, current_value, historical_value)
   ```

4. **Smart Alerting (Minimizing False Alarms):**
   ```python
   class SmartAlertEngine:
       """
       200+ models × 10+ metrics = 2000+ time series.
       Challenge: Alert fatigue. Oncall ignores alerts if too many false positives.
       """
       
       def __init__(self):
           self.alert_history = AlertHistory()
           self.suppression_rules = []
       
       def should_alert(self, metric_name, model_id, current_value) -> bool:
           # Adaptive thresholds (not static!)
           threshold = self.compute_adaptive_threshold(
               metric_name, model_id, 
               method='iqr',  # Interquartile range method
               lookback_days=30,
               sensitivity=3.0  # 3 sigma equivalent
           )
           
           if current_value < threshold:
               return False
           
           # Confirm persistence (not just a blip)
           if not self.is_persistent(metric_name, model_id, duration='15min'):
               return False
           
           # Check for known causes (suppress if expected)
           if self.is_expected_anomaly(metric_name, model_id):
               # E.g., known deploy, holiday traffic pattern, scheduled maintenance
               return False
           
           # Rate limit per model (max 1 alert per model per hour)
           if self.alert_history.recent_alert(model_id, window='1h'):
               self.aggregate_alert(model_id, metric_name)
               return False
           
           return True
       
       def compute_adaptive_threshold(self, metric, model_id, method, lookback_days, sensitivity):
           """Thresholds that adapt to each model's normal behavior."""
           historical = self.get_historical_values(metric, model_id, lookback_days)
           
           if method == 'iqr':
               q25, q75 = np.percentile(historical, [25, 75])
               iqr = q75 - q25
               lower_bound = q25 - sensitivity * iqr
               upper_bound = q75 + sensitivity * iqr
               return (lower_bound, upper_bound)
           
           elif method == 'seasonal':
               # Account for daily/weekly patterns
               seasonal_component = self.decompose_seasonality(historical)
               residuals = historical - seasonal_component
               threshold = residuals.std() * sensitivity
               return threshold
   ```

5. **Automated Root Cause Analysis:**
   ```python
   class AutoRootCauseAnalysis:
       """When alert fires, automatically identify probable cause."""
       
       def analyze(self, model_id, alert):
           """Check common failure modes in priority order."""
           
           causes = []
           
           # Check 1: Was there a recent model deploy?
           recent_deploy = self.check_recent_deploy(model_id, window='2h')
           if recent_deploy:
               causes.append(('model_deploy', 0.9, recent_deploy))
           
           # Check 2: Data pipeline issues?
           data_health = self.check_data_pipeline(model_id)
           if not data_health.healthy:
               causes.append(('data_pipeline', 0.85, data_health.issues))
           
           # Check 3: Feature store issues?
           feature_health = self.check_feature_freshness(model_id)
           if not feature_health.healthy:
               causes.append(('stale_features', 0.8, feature_health.stale_features))
           
           # Check 4: Upstream dependency change?
           upstream_changes = self.check_upstream_changes(model_id, window='24h')
           if upstream_changes:
               causes.append(('upstream_change', 0.7, upstream_changes))
           
           # Check 5: Distribution shift in input data?
           drift_report = self.compute_feature_drift(model_id)
           if drift_report.significant_drift:
               causes.append(('input_drift', 0.6, drift_report.drifted_features))
           
           # Check 6: Infrastructure issue?
           infra_health = self.check_infrastructure(model_id)
           if not infra_health.healthy:
               causes.append(('infrastructure', 0.5, infra_health.issues))
           
           # Rank causes by probability
           causes.sort(key=lambda x: x[1], reverse=True)
           
           return RootCauseReport(
               model_id=model_id,
               alert=alert,
               probable_causes=causes,
               recommended_action=self.recommend_action(causes[0] if causes else None)
           )
   ```

---

## Question 50: Adversarial Robustness in Production ML
**Difficulty: Staff Level | Topic: ML Security | Asked at: Google, Microsoft, Tesla, Financial Institutions**

Design a system to defend production ML models against adversarial attacks (evasion, poisoning, model extraction). How do you detect attacks in real-time? What's the trade-off between robustness and accuracy? Design defense-in-depth for a fraud detection system.

### Expected Answer:

**Adversarial Defense Architecture:**

1. **Attack Taxonomy & Defenses:**
   ```
   ┌─────────────────────────────────────────────────────┐
   │            ML Attack Vectors                          │
   ├─────────────────────────────────────────────────────┤
   │ Evasion: Modify inputs to fool the model            │
   │   → Defense: Adversarial training, input validation  │
   │                                                      │
   │ Poisoning: Corrupt training data                    │
   │   → Defense: Data validation, robust statistics      │
   │                                                      │
   │ Model Extraction: Steal model via queries           │
   │   → Defense: Rate limiting, query detection          │
   │                                                      │
   │ Privacy: Extract training data from model           │
   │   → Defense: DP training, membership inference test  │
   │                                                      │
   │ Backdoor: Hidden trigger in trained model           │
   │   → Defense: Neural cleanse, fine-pruning            │
   └─────────────────────────────────────────────────────┘
   ```

2. **Real-Time Attack Detection:**
   ```python
   class AdversarialDetector:
       """Detect adversarial inputs at inference time."""
       
       def detect(self, input_features, model_output) -> DetectionResult:
           signals = []
           
           # Method 1: Input statistical test
           # Adversarial examples often lie in low-density regions
           density = self.density_estimator.score(input_features)
           if density < self.density_threshold:
               signals.append(('low_density', density))
           
           # Method 2: Prediction uncertainty
           # Adversarial examples often have unusual uncertainty patterns
           mc_dropout_preds = self.mc_dropout_inference(input_features, n=10)
           uncertainty = mc_dropout_preds.std()
           if uncertainty > self.uncertainty_threshold:
               signals.append(('high_uncertainty', uncertainty))
           
           # Method 3: Feature squeezing
           # Compare predictions on original vs. simplified input
           squeezed_input = self.squeeze_features(input_features)
           original_pred = model_output
           squeezed_pred = self.model.predict(squeezed_input)
           prediction_diff = abs(original_pred - squeezed_pred)
           if prediction_diff > self.squeeze_threshold:
               signals.append(('squeeze_mismatch', prediction_diff))
           
           # Method 4: Ensemble disagreement
           # Adversarial examples that fool one model often don't fool others
           ensemble_preds = [m.predict(input_features) for m in self.ensemble]
           disagreement = np.std(ensemble_preds)
           if disagreement > self.ensemble_threshold:
               signals.append(('ensemble_disagreement', disagreement))
           
           is_adversarial = len(signals) >= 2  # Multiple signals = high confidence
           return DetectionResult(is_adversarial, signals)
   ```

3. **Adversarial Training for Robustness:**
   ```python
   class AdversarialTrainer:
       """Train model to be robust against adversarial perturbations."""
       
       def train_step(self, batch):
           features, labels = batch
           
           # Generate adversarial examples (PGD attack)
           adv_features = self.pgd_attack(features, labels, 
                                          epsilon=0.1, 
                                          steps=10, 
                                          step_size=0.02)
           
           # Train on both clean and adversarial examples
           clean_loss = self.model.compute_loss(features, labels)
           adv_loss = self.model.compute_loss(adv_features, labels)
           
           # Combined loss (lambda controls robustness-accuracy trade-off)
           total_loss = (1 - self.lambda_adv) * clean_loss + self.lambda_adv * adv_loss
           
           total_loss.backward()
           self.optimizer.step()
       
       def pgd_attack(self, features, labels, epsilon, steps, step_size):
           """Projected Gradient Descent - strongest first-order attack."""
           adv = features.clone().requires_grad_(True)
           
           for _ in range(steps):
               loss = self.model.compute_loss(adv, labels)
               grad = torch.autograd.grad(loss, adv)[0]
               
               # Step in direction of increasing loss
               adv = adv + step_size * grad.sign()
               
               # Project back into epsilon-ball around original
               perturbation = adv - features
               perturbation = perturbation.clamp(-epsilon, epsilon)
               adv = features + perturbation
               adv = adv.clamp(0, 1)  # Keep in valid input range
           
           return adv.detach()
   ```

4. **Model Extraction Defense:**
   ```python
   class ModelExtractionDefense:
       """Detect and prevent model stealing via API queries."""
       
       def __init__(self):
           self.query_analyzer = QueryPatternAnalyzer()
           self.watermark = ModelWatermark()
       
       def monitor_queries(self, user_id, query):
           """Detect extraction attempts in real-time."""
           user_history = self.get_query_history(user_id)
           
           # Signal 1: Query volume anomaly
           if self.query_rate(user_id, window='1h') > self.rate_threshold:
               self.flag_user(user_id, 'high_volume')
           
           # Signal 2: Systematic exploration pattern
           # Extractors query along grid/boundary regions
           if self.detect_grid_pattern(user_history):
               self.flag_user(user_id, 'grid_exploration')
           
           # Signal 3: Queries near decision boundary
           # Attackers probe the boundary to reconstruct it
           boundary_ratio = self.compute_boundary_query_ratio(user_history)
           if boundary_ratio > 0.3:
               self.flag_user(user_id, 'boundary_probing')
           
           # Defense: Add calibrated noise to outputs for suspicious users
           if self.is_flagged(user_id):
               return self.add_defensive_noise(query)
       
       def add_defensive_noise(self, prediction):
           """Add noise that degrades extraction without hurting normal use."""
           # For classification: occasionally flip low-confidence predictions
           # For regression: add small random perturbation
           noise = np.random.normal(0, self.noise_std)
           return prediction + noise
       
       def embed_watermark(self, model):
           """Embed watermark to prove ownership if model is stolen."""
           # Train model to produce specific outputs on secret trigger inputs
           trigger_set = self.generate_trigger_inputs(n=100)
           trigger_labels = self.generate_trigger_labels(n=100)
           
           # Fine-tune on triggers (doesn't affect normal performance)
           self.fine_tune(model, trigger_set, trigger_labels, epochs=10)
           
           return model  # Can verify ownership by querying with triggers
   ```

5. **Defense-in-Depth for Fraud Detection:**
   ```python
   class FraudModelDefenseStack:
       """
       Fraud models face sophisticated adversaries (organized crime).
       They actively try to evade detection.
       """
       
       def predict_with_defense(self, transaction):
           # Layer 1: Rule-based pre-filters (can't be evaded by gradient attacks)
           if self.rule_engine.is_obviously_fraud(transaction):
               return FraudDecision(score=1.0, reason='rule_match')
           
           # Layer 2: Multiple diverse models (harder to evade all simultaneously)
           scores = {
               'gradient_boosted': self.gbm_model.predict(transaction),
               'neural_network': self.nn_model.predict(transaction),
               'graph_model': self.graph_model.predict(transaction),  # Social network features
               'sequence_model': self.lstm_model.predict(transaction),  # Temporal patterns
           }
           
           # Layer 3: Ensemble with adversarial diversity
           # Models trained on different features → evading one doesn't evade others
           ensemble_score = self.adversarial_ensemble(scores)
           
           # Layer 4: Behavioral consistency check
           # Does this transaction fit the user's historical pattern?
           consistency = self.check_behavioral_consistency(transaction)
           
           # Layer 5: Velocity checks (rule-based, robust)
           velocity_score = self.velocity_checks(transaction)
           
           # Final decision: Multiple signals must agree
           final_score = self.combine_with_minimum_agreement(
               [ensemble_score, consistency, velocity_score],
               min_agreeing=2
           )
           
           return FraudDecision(score=final_score)
       
       def adversarial_ensemble(self, individual_scores):
           """
           Key insight: Train models to be DIVERSE, not just accurate.
           If attacker evades model A, model B (trained differently) catches them.
           
           Diversity strategies:
           - Different feature subsets
           - Different training data samples
           - Different model architectures
           - Different loss functions
           - Adversarially trained vs standard
           """
           # Require majority agreement
           fraud_votes = sum(1 for s in individual_scores.values() if s > 0.5)
           return fraud_votes / len(individual_scores)
   ```
# Hallucination Detection & Mitigation - Staff Architect Interview

## Question 61: Hallucination Taxonomy and Detection
**Difficulty: Staff Level | Topic: LLM Reliability | Asked at: OpenAI, Anthropic, Google**

Classify the different types of hallucinations in LLM systems. Design a multi-layer detection system that identifies hallucinations in real-time with <100ms overhead.

### Expected Answer:

**Hallucination Taxonomy:**

1. **Types of Hallucinations:**
   | Type | Description | Example | Detection Difficulty |
   |------|-------------|---------|---------------------|
   | Intrinsic | Contradicts source material | "The paper says X" when paper says Y | Medium (NLI) |
   | Extrinsic | Not supported by any source | Fabricating citations/facts | Hard |
   | Factual | Incorrect real-world facts | "Paris is the capital of Germany" | Medium (KB lookup) |
   | Faithfulness | Doesn't match retrieved context | RAG returns A, LLM says B | Medium (NLI) |
   | Logical | Invalid reasoning/inference | "A implies B, B implies C, therefore A implies D" | Hard |
   | Temporal | Wrong time attribution | "GPT-4 was released in 2020" | Medium (date check) |
   | Entity | Wrong entity substitution | Confusing similar named entities | Medium (NER) |

2. **Multi-Layer Detection Architecture:**
   ```
   LLM Response
        │
        ▼
   ┌─────────────────────────────────────────────┐
   │ Layer 1: Statistical Detection (5ms)         │
   │ - Token probability analysis                  │
   │ - Entropy spikes in generation               │
   │ - Repetition/degeneration detection           │
   └─────────────────────┬───────────────────────┘
                         │
   ┌─────────────────────▼───────────────────────┐
   │ Layer 2: NLI-Based Faithfulness (30ms)       │
   │ - Check each claim against retrieved context  │
   │ - Entailment/Contradiction/Neutral scoring    │
   └─────────────────────┬───────────────────────┘
                         │
   ┌─────────────────────▼───────────────────────┐
   │ Layer 3: Claim Decomposition (50ms)          │
   │ - Break response into atomic claims           │
   │ - Verify each claim independently            │
   │ - Confidence scoring per claim               │
   └─────────────────────┬───────────────────────┘
                         │
   ┌─────────────────────▼───────────────────────┐
   │ Layer 4: Knowledge Base Verification (async)  │
   │ - Check against structured KB                 │
   │ - Entity validation                          │
   │ - Temporal fact checking                      │
   └─────────────────────────────────────────────┘
   ```

3. **Implementation:**
   ```python
   class HallucinationDetector:
       def __init__(self):
           self.nli_model = load_model('deberta-v3-large-mnli')  # Fast NLI
           self.claim_extractor = ClaimExtractor()
           self.kb_checker = KnowledgeBaseChecker()
       
       async def detect(self, response: str, context: List[str], 
                       latency_budget_ms: int = 100) -> HallucinationReport:
           
           # Layer 1: Fast statistical checks (always run)
           stats = self.statistical_check(response)
           if stats.is_degenerate:
               return HallucinationReport(hallucinated=True, type='degenerate')
           
           # Layer 2: NLI faithfulness (always run, <30ms)
           nli_scores = self.nli_check(response, context)
           
           # Layer 3: Claim verification (if budget allows)
           claims = []
           if latency_budget_ms > 50:
               claims = self.claim_extractor.extract(response)
               claim_scores = await self.verify_claims(claims, context)
           
           # Aggregate results
           return HallucinationReport(
               overall_faithfulness=nli_scores.mean(),
               hallucinated_claims=[c for c in claims if c.score < 0.5],
               confidence=self.aggregate_confidence(stats, nli_scores, claim_scores)
           )
       
       def nli_check(self, response: str, context: List[str]) -> np.ndarray:
           """Check if response is entailed by context."""
           combined_context = " ".join(context[:3])  # Top 3 for speed
           
           # Sentence-level NLI
           response_sentences = self.split_sentences(response)
           scores = []
           for sentence in response_sentences:
               result = self.nli_model.predict(
                   premise=combined_context,
                   hypothesis=sentence
               )
               # result: {entailment: 0.8, contradiction: 0.1, neutral: 0.1}
               scores.append(result['entailment'])
           
           return np.array(scores)
   ```

4. **Confidence Calibration:**
   - Train threshold on labeled dataset (1000+ examples)
   - Different thresholds for different use cases:
     - Medical: Conservative (flag if confidence < 0.9)
     - Casual chat: Lenient (flag if confidence < 0.5)
   - Bayesian calibration: Convert raw scores to calibrated probabilities

5. **Handling Detected Hallucinations:**
   | Severity | Action | User Experience |
   |----------|--------|-----------------|
   | Low (single uncertain claim) | Add qualifier | "Based on available information..." |
   | Medium (unsupported but plausible) | Add disclaimer | "Note: I couldn't verify..." |
   | High (contradicts sources) | Remove claim | Regenerate without hallucinated part |
   | Critical (dangerous misinformation) | Block response | "I cannot provide a reliable answer" |

---

## Question 62: Grounded Generation Architecture
**Difficulty: Staff Level | Topic: Faithfulness | Asked at: Google, Microsoft, Anthropic**

Design a generation system that guarantees factual grounding - every claim in the output must be traceable to a source document. How do you architect "attribution-by-design" rather than post-hoc fact-checking?

### Expected Answer:

**Attribution-by-Design Architecture:**

1. **Core Principle:** Never generate ungrounded text. Every sentence must cite a source.

2. **Constrained Generation Pipeline:**
   ```python
   class GroundedGenerator:
       def generate(self, query: str, sources: List[Document]) -> AttributedResponse:
           # Step 1: Extract citable facts from sources
           fact_database = self.extract_facts(sources)
           # [{fact: "Revenue grew 15%", source: doc_3, para: 2}, ...]
           
           # Step 2: Plan response structure
           outline = self.plan_response(query, fact_database)
           # [{point: "Revenue growth", supporting_facts: [fact_1, fact_3]}, ...]
           
           # Step 3: Generate with inline citations
           response = self.generate_with_citations(outline, fact_database)
           
           # Step 4: Verify all citations are valid
           verified = self.verify_citations(response, sources)
           
           return verified
       
       def generate_with_citations(self, outline, facts):
           """
           Prompt engineering for grounded generation:
           
           Instructions: Generate a response using ONLY the provided facts.
           Every sentence must end with a citation [Source X].
           If you cannot answer from the provided facts, say "Not found in sources."
           
           Available Facts:
           [1] Revenue grew 15% YoY (Source: Q3 Report, p.4)
           [2] Customer count reached 10M (Source: Press Release, Jan 2024)
           ...
           
           DO NOT state anything not directly supported by the facts above.
           """
           prompt = self.build_grounded_prompt(outline, facts)
           return self.llm.generate(prompt)
   ```

3. **Fact Extraction & Indexing:**
   ```python
   class FactExtractor:
       def extract_facts(self, documents: List[Document]) -> FactDatabase:
           facts = []
           for doc in documents:
               for paragraph in doc.paragraphs:
                   # Extract atomic claims
                   claims = self.decompose_to_claims(paragraph)
                   for claim in claims:
                       facts.append(Fact(
                           text=claim.text,
                           source_doc=doc.id,
                           source_paragraph=paragraph.id,
                           source_page=paragraph.page,
                           entities=claim.entities,
                           confidence=claim.confidence,
                           temporal_scope=claim.time_reference
                       ))
           
           return FactDatabase(facts)
   ```

4. **Citation Verification:**
   ```python
   class CitationVerifier:
       def verify(self, response: AttributedResponse, sources: List[Document]):
           for sentence in response.sentences:
               if not sentence.has_citation:
                   # Ungrounded sentence! 
                   if self.is_transitional(sentence):
                       pass  # "In summary..." doesn't need citation
                   else:
                       sentence.mark_ungrounded()
               else:
                   # Verify citation accuracy
                   cited_source = sources[sentence.citation_id]
                   entailment = self.nli_check(
                       premise=cited_source.text,
                       hypothesis=sentence.text
                   )
                   if entailment < 0.7:
                       sentence.mark_misattributed()
           
           return response
   ```

5. **Production Trade-offs:**
   - Grounded generation is more conservative (may miss useful inferences)
   - Latency: +100-200ms for fact extraction and verification
   - Quality: Higher precision, lower recall (won't state useful obvious facts without source)
   - User experience: Citations add visual noise but build trust
   - Hybrid: Allow parametric knowledge for "common knowledge" with lower citation requirements

---

## Question 63: Hallucination in Multi-Step Reasoning
**Difficulty: Staff Level | Topic: Chain-of-Thought Reliability | Asked at: Google DeepMind, OpenAI**

LLMs hallucinate more in multi-step reasoning chains. Design a system that detects and prevents hallucination at each reasoning step, ensuring the final answer is reliable even for complex 5+ step reasoning tasks.

### Expected Answer:

**Verified Chain-of-Thought Architecture:**

1. **Problem Statement:**
   - Each reasoning step has P(correct) ≈ 0.9
   - For 5 steps: P(all correct) = 0.9^5 = 0.59 (41% error rate!)
   - Need: Verify each step independently

2. **Step-Level Verification:**
   ```python
   class VerifiedReasoningChain:
       def reason(self, query: str, context: str) -> VerifiedAnswer:
           steps = []
           current_context = context
           
           for i in range(self.max_steps):
               # Generate next reasoning step
               step = self.generate_step(query, current_context, steps)
               
               if step.is_conclusion:
                   break
               
               # Verify this step
               verification = self.verify_step(step, current_context, steps)
               
               if verification.valid:
                   steps.append(step)
                   current_context += f"\nVerified: {step.text}"
               else:
                   # Step is invalid - try alternative reasoning
                   alternative = self.generate_alternative_step(
                       query, current_context, steps, 
                       invalid_step=step,
                       reason=verification.failure_reason
                   )
                   if self.verify_step(alternative, current_context, steps).valid:
                       steps.append(alternative)
                   else:
                       # Cannot find valid next step
                       return VerifiedAnswer(
                           answer=None,
                           confidence=0.0,
                           failure_point=i,
                           reason="Could not verify reasoning step"
                       )
           
           return VerifiedAnswer(
               answer=steps[-1].conclusion,
               confidence=self.chain_confidence(steps),
               reasoning_chain=steps
           )
   ```

3. **Step Verification Methods:**
   ```python
   class StepVerifier:
       def verify_step(self, step, context, previous_steps):
           checks = []
           
           # Check 1: Logical consistency with previous steps
           checks.append(self.logical_consistency(step, previous_steps))
           
           # Check 2: Factual grounding in context
           checks.append(self.factual_grounding(step, context))
           
           # Check 3: Mathematical/logical validity
           if step.has_calculation:
               checks.append(self.verify_calculation(step))
           
           # Check 4: Self-consistency (generate same step 3 times)
           alternatives = [self.generate_step_fresh() for _ in range(3)]
           consistency = self.measure_agreement(step, alternatives)
           checks.append(consistency > 0.7)
           
           return VerificationResult(
               valid=all(checks),
               confidence=min(c.score for c in checks),
               failure_reason=next((c.reason for c in checks if not c.passed), None)
           )
   ```

4. **Beam Search over Reasoning Paths:**
   ```
   Query: "What's the ROI of implementing RAG vs fine-tuning?"
   
   Path A (beam 1):              Path B (beam 2):
   Step 1: Calculate RAG cost    Step 1: Define ROI metrics
   Step 2: Calculate FT cost     Step 2: Calculate RAG cost
   Step 3: Compare quality       Step 3: Calculate FT cost  
   Step 4: Calculate ROI         Step 4: Compare quality + cost
   ✓ Verified                    ✓ Verified
   
   → Select highest-confidence path
   ```

5. **Production Implementation:**
   - Use smaller/cheaper model for verification (GPT-3.5 verifies GPT-4 steps)
   - Parallel verification: While generating step N+1, verify step N
   - Cache verified reasoning patterns (common reasoning chains)
   - Latency: 2-3x single generation (acceptable for complex queries)
   - Fallback: If no path verifies, return "Unable to determine" with partial analysis

---

## Question 64: Reducing Hallucination Through Retrieval Optimization
**Difficulty: Staff Level | Topic: RAG Quality | Asked at: Anthropic, Cohere, Microsoft**

Studies show that irrelevant retrieved context INCREASES hallucination rates. Design a retrieval quality optimization system that minimizes hallucination by ensuring only high-quality, relevant context reaches the LLM.

### Expected Answer:

**Retrieval Quality Optimization for Hallucination Reduction:**

1. **The Counter-Intuitive Problem:**
   - More context ≠ less hallucination
   - Irrelevant context confuses the LLM → MORE hallucination
   - Contradictory context → LLM makes up a "middle ground" (hallucination)
   - Partial information → LLM fills gaps with fabrication

2. **Quality-First Retrieval Pipeline:**
   ```python
   class QualityOptimizedRetriever:
       def retrieve(self, query: str) -> List[Document]:
           # Step 1: Over-retrieve
           candidates = self.vector_search(query, top_k=50)
           
           # Step 2: Relevance filtering (strict threshold)
           relevant = [doc for doc in candidates 
                      if doc.similarity_score > self.relevance_threshold]
           # threshold = 0.75 (learned from hallucination correlation data)
           
           # Step 3: Contradiction detection
           non_contradictory = self.remove_contradictions(relevant)
           
           # Step 4: Completeness assessment
           if self.information_sufficient(query, non_contradictory):
               return non_contradictory[:5]
           else:
               # Better to return nothing than partial info
               return self.annotated_return(
                   non_contradictory, 
                   gaps=self.identify_gaps(query, non_contradictory)
               )
       
       def remove_contradictions(self, documents):
           """Remove documents that contradict the majority."""
           claims_per_doc = [self.extract_claims(doc) for doc in documents]
           
           for i, doc_claims in enumerate(claims_per_doc):
               for claim in doc_claims:
                   contradictions = sum(
                       1 for j, other_claims in enumerate(claims_per_doc)
                       if i != j and self.contradicts(claim, other_claims)
                   )
                   if contradictions > len(documents) * 0.3:
                       documents[i].flag_contradictory(claim)
           
           return [doc for doc in documents if not doc.has_contradictions]
   ```

3. **Context Quality Scoring:**
   | Quality Signal | Weight | Measurement |
   |---------------|--------|-------------|
   | Relevance to query | 0.30 | Cross-encoder score |
   | Information density | 0.20 | Unique facts per token |
   | Source authority | 0.15 | Document trust score |
   | Freshness | 0.15 | Document age penalty |
   | Completeness | 0.10 | Covers all query aspects |
   | Consistency | 0.10 | No contradictions with other docs |

4. **Hallucination-Aware Prompt Design:**
   ```python
   ANTI_HALLUCINATION_PROMPT = """
   Answer the question using ONLY the provided context.
   
   Rules:
   1. If the context doesn't contain the answer, say "The provided documents don't contain this information."
   2. If the context partially answers the question, answer only what's supported and explicitly state what's missing.
   3. Never extrapolate beyond what's explicitly stated.
   4. If documents contradict each other, present both views with sources.
   5. Prefix uncertain statements with "Based on limited information..."
   
   Context quality note: {context_quality_assessment}
   - Coverage: {coverage_percentage}% of query aspects covered
   - Gaps: {identified_gaps}
   
   Context:
   {filtered_context}
   
   Question: {query}
   """
   ```

5. **Feedback Loop for Threshold Optimization:**
   - Log (query, context, response, hallucination_detected) tuples
   - Correlate relevance thresholds with hallucination rates
   - Automatically adjust thresholds to minimize hallucination while maintaining answer rate
   - Target: <2% hallucination rate with >85% answer rate

---

## Question 65: Hallucination Benchmarking and Red-Teaming
**Difficulty: Staff Level | Topic: Evaluation | Asked at: Anthropic, OpenAI, Google DeepMind**

Design a comprehensive hallucination benchmarking framework and red-teaming strategy for a production RAG system serving healthcare information. Include synthetic adversarial test generation.

### Expected Answer:

**Healthcare RAG Hallucination Benchmarking:**

1. **Benchmark Categories:**
   | Category | Description | Example | Risk Level |
   |----------|-------------|---------|------------|
   | Drug interactions | Incorrect drug combo safety | "X and Y are safe together" (they're not) | Critical |
   | Dosage hallucination | Wrong dosage information | "Take 500mg" (correct is 50mg) | Critical |
   | Symptom attribution | Wrong disease for symptoms | "Chest pain = anxiety" (could be cardiac) | High |
   | Outdated guidelines | Citing superseded protocols | Using 2015 guidelines when 2023 exist | Medium |
   | Entity confusion | Mixing up similar drugs | Confusing Metformin with Methotrexate | Critical |
   | Statistical fabrication | Inventing study results | "Studies show 95% efficacy" (no such study) | High |

2. **Adversarial Test Generation:**
   ```python
   class HealthcareRedTeamGenerator:
       def generate_adversarial_tests(self) -> List[TestCase]:
           tests = []
           
           # Type 1: Confusion pairs (similar names, different drugs)
           confusion_pairs = [
               ("metformin", "methotrexate"),
               ("hydroxyzine", "hydroxychloroquine"),
               ("prednisone", "prednisolone")
           ]
           for drug_a, drug_b in confusion_pairs:
               tests.append(TestCase(
                   query=f"What are the side effects of {drug_a}?",
                   expected_answer_about=drug_a,
                   hallucination_if_mentions=drug_b,
                   category='entity_confusion'
               ))
           
           # Type 2: Boundary conditions (max doses, contraindications)
           for drug in self.drug_database:
               tests.append(TestCase(
                   query=f"What is the maximum daily dose of {drug.name}?",
                   ground_truth=drug.max_dose,
                   tolerance=0,  # Must be exact
                   category='dosage'
               ))
           
           # Type 3: Temporal traps (outdated info)
           for guideline in self.guidelines_with_updates:
               tests.append(TestCase(
                   query=f"What is the current recommendation for {guideline.topic}?",
                   current_answer=guideline.current_version,
                   outdated_answer=guideline.previous_version,
                   hallucination_if_matches='outdated',
                   category='temporal'
               ))
           
           # Type 4: Non-existent entities (should refuse)
           tests.append(TestCase(
               query="What are the indications for Fakemedicil 500mg?",
               expected="refuse_or_state_unknown",
               hallucination_if="provides_any_medical_info",
               category='fabrication'
           ))
           
           return tests
   ```

3. **Automated Red-Team Pipeline:**
   ```
   Monthly Red-Team Cycle:
   1. Generate 500 adversarial queries (LLM-generated + template-based)
   2. Run against production system (shadow mode)
   3. Automated grading (NLI + rule-based + expert review)
   4. Report: Hallucination rate by category
   5. Root cause analysis for new failure modes
   6. Update guardrails and retrieval thresholds
   7. Regression test: Verify previous failures are fixed
   ```

4. **Scoring Framework:**
   ```python
   class HallucinationScorer:
       def score_response(self, response, test_case):
           score = {
               'factual_accuracy': self.check_facts(response, test_case.ground_truth),
               'citation_accuracy': self.verify_citations(response),
               'refusal_appropriateness': self.check_refusal(response, test_case),
               'entity_correctness': self.verify_entities(response, test_case),
               'temporal_accuracy': self.check_dates(response, test_case),
               'severity': self.assess_harm_potential(response, test_case)
           }
           
           # Healthcare-specific: any critical hallucination = immediate fail
           if score['severity'] == 'critical' and score['factual_accuracy'] < 1.0:
               score['overall'] = 0.0  # Zero tolerance for critical errors
           
           return score
   ```

5. **Continuous Monitoring in Production:**
   - Real-time hallucination detection on 100% of medical responses
   - Weekly human expert audit of 100 random responses
   - Monthly adversarial red-team exercises
   - Immediate alert on critical category hallucinations
   - Quarterly benchmark refresh (new drugs, updated guidelines)
   - Incident response: Any confirmed critical hallucination → system pause + investigation
