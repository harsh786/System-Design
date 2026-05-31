# ML Training Infrastructure - Staff Architect Interview

## Question 41: Distributed Training at Scale
**Difficulty: Staff Level | Topic: ML Infrastructure | Asked at: Meta, Google, NVIDIA, Microsoft**

Design a distributed training system for a 175B parameter model across 1024 GPUs. Explain data parallelism, tensor parallelism, pipeline parallelism, and expert parallelism (MoE). How do you handle stragglers, gradient synchronization, and checkpointing?

### Expected Answer:

**Distributed Training Architecture:**

1. **Parallelism Strategies Combined (3D Parallelism):**
   ```
   1024 GPUs organized as:
   - Data Parallel (DP): 16 replicas
   - Tensor Parallel (TP): 8 GPUs per node (NVLink)
   - Pipeline Parallel (PP): 8 stages across nodes
   
   Total: DP=16 × TP=8 × PP=8 = 1024 GPUs
   
   ┌────────── Data Parallel Group 1 ──────────┐
   │ ┌─── Pipeline Stage 1 ───┐                │
   │ │ GPU0 GPU1 GPU2 GPU3    │ (Tensor Par.)  │
   │ │ GPU4 GPU5 GPU6 GPU7    │                │
   │ └────────────────────────┘                │
   │ ┌─── Pipeline Stage 2 ───┐                │
   │ │ GPU8 GPU9 GPU10 GPU11  │                │
   │ │ GPU12 GPU13 GPU14 GPU15│                │
   │ └────────────────────────┘                │
   │ ... (8 pipeline stages)                    │
   └───────────────────────────────────────────┘
   × 16 data parallel replicas = 1024 GPUs
   ```

2. **Gradient Synchronization:**
   ```python
   class DistributedTrainer:
       def __init__(self, model, config):
           self.dp_size = config.dp_size  # 16
           self.tp_size = config.tp_size  # 8
           self.pp_size = config.pp_size  # 8
           
           # Communication groups
           self.dp_group = create_process_group(ranks=self.get_dp_peers())
           self.tp_group = create_process_group(ranks=self.get_tp_peers())
           self.pp_group = create_process_group(ranks=self.get_pp_peers())
       
       def training_step(self, batch):
           # 1. Split batch across DP dimension
           micro_batches = self.split_batch(batch, self.dp_size * self.pp_size)
           
           # 2. Pipeline schedule (1F1B - one forward, one backward)
           losses = self.pipeline_schedule(micro_batches)
           
           # 3. All-reduce gradients across DP group
           # (TP handles intra-node, PP handles inter-stage)
           for param in self.model.parameters():
               dist.all_reduce(param.grad, group=self.dp_group, op=dist.ReduceOp.AVG)
           
           # 4. Optimizer step
           self.optimizer.step()
           
           return sum(losses) / len(losses)
       
       def pipeline_schedule(self, micro_batches):
           """1F1B schedule minimizes pipeline bubble."""
           num_micro = len(micro_batches)
           num_warmup = self.pp_size - self.pp_rank - 1
           num_steady = num_micro - num_warmup
           
           losses = []
           
           # Warmup: only forward passes
           for i in range(num_warmup):
               output = self.forward_step(micro_batches[i])
               losses.append(output.loss)
           
           # Steady state: alternate 1 forward + 1 backward
           for i in range(num_steady):
               output = self.forward_step(micro_batches[num_warmup + i])
               losses.append(output.loss)
               self.backward_step(micro_batches[i])
           
           # Cooldown: only backward passes
           for i in range(num_warmup):
               self.backward_step(micro_batches[num_steady + i])
           
           return losses
   ```

3. **ZeRO (Zero Redundancy Optimizer):**
   ```python
   class ZeROOptimizer:
       """
       ZeRO Stage 3: Partition model parameters, gradients, AND optimizer states.
       Each GPU only stores 1/N of everything. All-gather when needed.
       
       Memory per GPU (175B model, FP16, 1024 GPUs):
       - Without ZeRO: 350GB (weights) + 350GB (grads) + 700GB (Adam states) = 1.4TB (impossible!)
       - ZeRO Stage 3: 1.4TB / 1024 = 1.37GB per GPU ✓ (fits in 80GB with room for activations)
       """
       
       def __init__(self, model, dp_group):
           self.dp_group = dp_group
           self.world_size = dist.get_world_size(dp_group)
           self.rank = dist.get_rank(dp_group)
           
           # Partition parameters
           self.param_partitions = self.partition_params(model)
       
       def forward_with_gather(self, module, input):
           """All-gather full parameters just-in-time for forward pass."""
           full_params = dist.all_gather(
               self.param_partitions[module], group=self.dp_group
           )
           module.load_params(full_params)
           output = module(input)
           module.free_params()  # Release full copy immediately
           return output
       
       def step(self):
           """Each GPU only updates its partition of parameters."""
           for partition_id in range(self.world_size):
               if partition_id == self.rank:
                   # This is my partition - update it
                   self.optimizer.step(self.param_partitions[partition_id])
               # Broadcast updated params to all
               dist.broadcast(self.param_partitions[partition_id], 
                            src=partition_id, group=self.dp_group)
   ```

4. **Checkpointing for Fault Tolerance:**
   ```python
   class AsyncCheckpointer:
       """
       Challenge: 175B model checkpoint = 350GB. Can't stop training for 10+ min.
       Solution: Async checkpointing with copy-on-write.
       """
       
       def __init__(self, save_interval_steps=500):
           self.interval = save_interval_steps
           self.checkpoint_executor = ThreadPoolExecutor(max_workers=2)
       
       def maybe_checkpoint(self, step, model, optimizer):
           if step % self.interval != 0:
               return
           
           # Snapshot model state (CPU copy, doesn't block training)
           state_dict = {
               'model': self.async_cpu_copy(model.state_dict()),
               'optimizer': self.async_cpu_copy(optimizer.state_dict()),
               'step': step,
               'rng_state': torch.cuda.get_rng_state(),
           }
           
           # Save in background (to distributed filesystem)
           future = self.checkpoint_executor.submit(
               self.save_checkpoint, state_dict, step
           )
           
           # Keep last 3 checkpoints, delete older
           self.cleanup_old_checkpoints(keep=3)
       
       def save_checkpoint(self, state_dict, step):
           """Distributed save: each rank saves its own shard."""
           rank = dist.get_rank()
           path = f's3://checkpoints/step_{step}/rank_{rank}.pt'
           torch.save(state_dict, path)
           
           # Rank 0 saves metadata
           if rank == 0:
               metadata = {
                   'step': step,
                   'world_size': dist.get_world_size(),
                   'timestamp': time.time(),
                   'loss': self.current_loss,
               }
               save_json(f's3://checkpoints/step_{step}/metadata.json', metadata)
       
       def restore(self, checkpoint_path):
           """Restore from checkpoint, handling world_size changes."""
           metadata = load_json(f'{checkpoint_path}/metadata.json')
           
           if metadata['world_size'] != dist.get_world_size():
               # Resharding needed (common when cluster changes)
               return self.restore_with_reshard(checkpoint_path, metadata)
           
           rank = dist.get_rank()
           state = torch.load(f'{checkpoint_path}/rank_{rank}.pt')
           return state
   ```

5. **Straggler Mitigation:**
   ```python
   class StragglerMitigation:
       """
       In 1024 GPU training, at least one GPU will be slow.
       A single slow GPU blocks all-reduce, wasting 1023 GPUs.
       """
       
       def detect_stragglers(self):
           """Monitor per-GPU step times."""
           step_times = self.collect_step_times()  # From all ranks
           median = np.median(step_times)
           
           stragglers = [
               rank for rank, time in enumerate(step_times)
               if time > median * 1.3  # 30% slower than median
           ]
           return stragglers
       
       def mitigate(self, stragglers):
           """Multiple mitigation strategies."""
           for rank in stragglers:
               # Strategy 1: Reduce batch size for slow GPU
               self.adjust_micro_batch_size(rank, factor=0.8)
               
               # Strategy 2: If persistent, exclude and use backup GPU
               if self.is_persistent_straggler(rank, window='10min'):
                   self.hot_swap_gpu(rank, replacement=self.get_spare_gpu())
               
               # Strategy 3: Gradient compression for slow network links
               if self.is_network_bottleneck(rank):
                   self.enable_gradient_compression(rank, ratio=0.1)
       
       def elastic_training(self):
           """Allow training to continue with fewer GPUs."""
           # If GPU fails, shrink DP group and continue
           # Adjust learning rate: lr_new = lr_old * (new_world_size / old_world_size)
           pass
   ```

---

## Question 42: Feature Store Design for Real-Time ML
**Difficulty: Staff Level | Topic: ML Platform | Asked at: Uber, Airbnb, Stripe, Netflix**

Design a feature store that serves features for both training (batch, historical) and inference (real-time, low-latency). How do you handle feature freshness, point-in-time correctness, and consistency between online and offline stores?

### Expected Answer:

**Feature Store Architecture:**

1. **Dual-Store Design:**
   ```
   ┌─────────────────────────────────────────────────────┐
   │                  Feature Store                        │
   ├──────────────────────┬──────────────────────────────┤
   │   Offline Store      │      Online Store             │
   │   (Training)         │      (Serving)                │
   │                      │                               │
   │   - Data Lake/DW     │   - Redis/DynamoDB            │
   │   - Full history     │   - Latest values only        │
   │   - High throughput  │   - Sub-10ms reads            │
   │   - Point-in-time    │   - Key-value lookup          │
   │     correctness      │   - Eventual consistency      │
   │   - Columnar format  │   - TTL-based expiry          │
   └──────────────────────┴──────────────────────────────┘
   
   Materialization Pipeline:
   Offline Store ──(scheduled/streaming)──▶ Online Store
   ```

2. **Point-in-Time Correctness (Training/Serving Skew Prevention):**
   ```python
   class PointInTimeJoin:
       """
       Critical: Training must use features AS THEY WERE at prediction time,
       not as they are NOW. Otherwise: data leakage / train-serve skew.
       """
       
       def get_training_features(self, entity_ids, timestamps, feature_names):
           """
           For each (entity, timestamp) pair, return feature values
           that were available AT that timestamp.
           """
           results = []
           for entity_id, ts in zip(entity_ids, timestamps):
               features = {}
               for feature in feature_names:
                   # Get the latest value BEFORE the timestamp
                   value = self.offline_store.query(
                       f"""
                       SELECT value FROM {feature.table}
                       WHERE entity_id = '{entity_id}'
                       AND event_timestamp <= '{ts}'
                       ORDER BY event_timestamp DESC
                       LIMIT 1
                       """
                   )
                   features[feature] = value
               results.append(features)
           return results
       
       def validate_no_leakage(self, feature_timestamps, label_timestamp):
           """Ensure no feature was computed AFTER the label was known."""
           for feat_ts in feature_timestamps:
               if feat_ts > label_timestamp:
                   raise DataLeakageError(
                       f"Feature timestamp {feat_ts} is after label "
                       f"timestamp {label_timestamp}"
                   )
   ```

3. **Real-Time Feature Computation:**
   ```python
   class StreamingFeatureEngine:
       """Compute features from event streams in real-time."""
       
       def __init__(self):
           self.stream_processor = FlinkJob()  # or Spark Structured Streaming
           self.aggregation_windows = ['1min', '5min', '1hr', '24hr', '7d']
       
       def define_feature(self, name, entity_key, aggregation, source_stream):
           """
           Example: user_purchase_count_1hr
           - Entity: user_id
           - Aggregation: COUNT
           - Window: 1 hour
           - Source: purchase_events stream
           """
           return StreamingFeature(
               name=name,
               entity_key=entity_key,
               aggregation=aggregation,
               source=source_stream,
               windows=self.aggregation_windows
           )
       
       def process_event(self, event):
           """Process incoming event, update all affected features."""
           entity_id = event[self.entity_key]
           
           for window in self.aggregation_windows:
               key = f"{self.name}:{entity_id}:{window}"
               
               if self.aggregation == 'count':
                   self.online_store.increment(key)
               elif self.aggregation == 'sum':
                   self.online_store.increment(key, event['amount'])
               elif self.aggregation == 'avg':
                   self.online_store.update_running_avg(key, event['value'])
               
               # Set TTL to window duration
               self.online_store.set_ttl(key, window_to_seconds(window))
           
           # Also write to offline store for historical access
           self.offline_store.append(entity_id, event, timestamp=event['ts'])
   ```

4. **Feature Consistency Monitoring:**
   ```python
   class FeatureConsistencyMonitor:
       """Detect drift between online and offline feature values."""
       
       def check_online_offline_consistency(self):
           """Periodically compare online vs offline values."""
           # Sample entities
           sample_entities = self.sample_active_entities(n=1000)
           
           discrepancies = []
           for entity_id in sample_entities:
               online_values = self.online_store.get_all_features(entity_id)
               offline_values = self.offline_store.get_latest_features(entity_id)
               
               for feature_name in online_values:
                   online_val = online_values[feature_name]
                   offline_val = offline_values.get(feature_name)
                   
                   if not self.values_match(online_val, offline_val, tolerance=0.01):
                       discrepancies.append({
                           'entity': entity_id,
                           'feature': feature_name,
                           'online': online_val,
                           'offline': offline_val,
                       })
           
           if len(discrepancies) / len(sample_entities) > 0.05:
               self.alert("Online/offline feature skew > 5%!")
           
           return discrepancies
       
       def check_feature_freshness(self):
           """Ensure online features are being updated."""
           for feature in self.registered_features:
               last_update = self.online_store.get_last_update_time(feature)
               expected_freshness = feature.sla_seconds
               
               if time.time() - last_update > expected_freshness:
                   self.alert(f"Feature {feature.name} is stale: "
                            f"last update {time.time() - last_update}s ago")
   ```

5. **Feature Registry & Discovery:**
   ```python
   class FeatureRegistry:
       """Central catalog of all features with lineage and metadata."""
       
       def register_feature(self, feature_def: FeatureDefinition):
           self.catalog.store({
               'name': feature_def.name,
               'entity': feature_def.entity_type,  # user, item, session
               'dtype': feature_def.dtype,
               'description': feature_def.description,
               'owner': feature_def.team,
               'source': feature_def.data_source,
               'freshness_sla': feature_def.freshness_sla,
               'computation': feature_def.transform_logic,
               'lineage': {
                   'upstream_tables': feature_def.dependencies,
                   'downstream_models': [],  # Auto-populated
               },
               'statistics': {
                   'mean': None, 'std': None, 'null_rate': None,
                   'distribution': None,  # Updated daily
               },
               'created_at': time.time(),
               'version': feature_def.version,
           })
       
       def search_features(self, query: str) -> List[Feature]:
           """Semantic search over feature descriptions."""
           return self.vector_index.search(query, top_k=20)
       
       def get_feature_lineage(self, feature_name):
           """Full lineage: raw data → transforms → feature → models → predictions."""
           pass
   ```

---

## Question 43: ML Model Versioning and Experiment Tracking
**Difficulty: Staff Level | Topic: MLOps | Asked at: Weights & Biases, MLflow, Google, Netflix**

Design a model registry and experiment tracking system that handles 1000+ concurrent experiments, supports model lineage from data to deployment, and enables reproducibility. How do you handle model promotion workflows and rollback?

### Expected Answer:

**Model Registry & Experiment Tracking System:**

1. **System Architecture:**
   ```
   ┌──────────────────────────────────────────────────────┐
   │                Experiment Tracking                     │
   │  (Metrics, Params, Artifacts, Code Versions)          │
   └───────────────────────┬──────────────────────────────┘
                           │ promotes
                           ▼
   ┌──────────────────────────────────────────────────────┐
   │                  Model Registry                        │
   │  (Versioned Models, Metadata, Lineage)                │
   └───────────────────────┬──────────────────────────────┘
                           │ deploys
                           ▼
   ┌──────────────────────────────────────────────────────┐
   │              Deployment Manager                        │
   │  (Canary, Shadow, A/B, Rollback)                      │
   └──────────────────────────────────────────────────────┘
   ```

2. **Experiment Tracking Schema:**
   ```python
   class ExperimentTracker:
       def create_run(self, experiment_name: str) -> Run:
           run = Run(
               id=generate_uuid(),
               experiment=experiment_name,
               # Automatic capture
               git_commit=get_current_commit(),
               git_branch=get_current_branch(),
               git_diff=get_uncommitted_changes(),
               environment={
                   'python_version': sys.version,
                   'packages': freeze_packages(),
                   'cuda_version': torch.version.cuda,
                   'gpu_type': get_gpu_info(),
               },
               code_snapshot=snapshot_source_files(),
               start_time=time.time(),
           )
           return run
       
       def log_params(self, run_id, params: dict):
           """Log hyperparameters (immutable after set)."""
           # params: learning_rate, batch_size, model_arch, etc.
           self.store.set_params(run_id, params)
       
       def log_metrics(self, run_id, metrics: dict, step: int):
           """Log time-series metrics."""
           # metrics: loss, accuracy, learning_rate (per step)
           self.store.append_metrics(run_id, metrics, step)
       
       def log_artifact(self, run_id, artifact_path, artifact_type):
           """Log model files, datasets, configs."""
           # Upload to artifact storage (S3/GCS)
           artifact_url = self.artifact_store.upload(artifact_path)
           self.store.register_artifact(run_id, artifact_url, artifact_type)
       
       def log_data_version(self, run_id, dataset_name, version_hash):
           """Track exact data used for training (reproducibility)."""
           self.store.set_data_lineage(run_id, dataset_name, version_hash)
   ```

3. **Model Promotion Workflow:**
   ```python
   class ModelPromotionPipeline:
       """
       Stages: Development → Staging → Canary → Production
       Each stage has gates that must pass before promotion.
       """
       
       STAGES = ['development', 'staging', 'canary', 'production']
       
       def promote(self, model_version: str, target_stage: str):
           current_stage = self.registry.get_stage(model_version)
           
           # Validate promotion order
           if self.STAGES.index(target_stage) - self.STAGES.index(current_stage) != 1:
               raise ValueError("Can only promote one stage at a time")
           
           # Run stage-specific gates
           gate_results = self.run_gates(model_version, target_stage)
           
           if all(g.passed for g in gate_results):
               self.registry.set_stage(model_version, target_stage)
               self.notify_stakeholders(model_version, target_stage)
           else:
               failed_gates = [g for g in gate_results if not g.passed]
               raise PromotionGateFailure(failed_gates)
       
       def run_gates(self, model_version, target_stage):
           gates = {
               'staging': [
                   self.gate_benchmark_regression(),   # No accuracy drop
                   self.gate_latency_requirement(),    # Meets SLA
                   self.gate_model_size_limit(),       # Fits in memory
                   self.gate_bias_fairness_check(),    # No bias regression
               ],
               'canary': [
                   self.gate_shadow_mode_validation(), # Tested on live traffic
                   self.gate_integration_tests(),      # Works with downstream
                   self.gate_security_scan(),          # No vulnerabilities
                   self.gate_approval_required(),      # Human sign-off
               ],
               'production': [
                   self.gate_canary_metrics_healthy(), # Canary showed no issues
                   self.gate_rollback_plan_exists(),   # Can revert if needed
                   self.gate_monitoring_configured(),  # Alerts are set up
               ],
           }
           return [gate(model_version) for gate in gates[target_stage]]
   ```

4. **Rollback Strategy:**
   ```python
   class ModelRollbackManager:
       def __init__(self):
           self.deployment_history = []  # Stack of deployed versions
       
       def deploy(self, model_version):
           """Deploy with automatic rollback capability."""
           previous_version = self.get_current_production()
           
           # Keep previous model warm (loaded, ready to serve)
           self.keep_warm(previous_version, ttl='24h')
           
           # Deploy new version
           self.deployment_history.append({
               'version': model_version,
               'deployed_at': time.time(),
               'previous': previous_version,
           })
           
           # Start automated monitoring
           self.start_canary_monitor(model_version, previous_version)
       
       def auto_rollback(self, model_version, reason):
           """Automatic rollback triggered by monitoring."""
           previous = self.get_previous_version(model_version)
           
           # Instant switch (previous model is warm)
           self.switch_traffic(to_version=previous, instant=True)
           
           # Mark version as failed
           self.registry.set_stage(model_version, 'failed')
           self.registry.add_note(model_version, f"Auto-rollback: {reason}")
           
           # Alert
           self.alert(
               severity='P1',
               message=f"Model {model_version} auto-rolled back: {reason}"
           )
       
       def canary_monitor(self, new_version, baseline_version):
           """Compare new vs baseline on live traffic."""
           metrics_new = self.collect_metrics(new_version, window='15min')
           metrics_baseline = self.get_baseline_metrics(baseline_version)
           
           # Statistical comparison
           for metric_name in ['accuracy', 'latency_p99', 'error_rate']:
               if self.is_significantly_worse(
                   metrics_new[metric_name], 
                   metrics_baseline[metric_name],
                   confidence=0.95
               ):
                   self.auto_rollback(new_version, 
                                     f"{metric_name} degraded significantly")
                   return
   ```

5. **Reproducibility Guarantees:**
   ```python
   class ReproducibilityManager:
       """Ensure any experiment can be exactly reproduced."""
       
       def capture_full_lineage(self, run_id):
           """Capture everything needed to reproduce."""
           return {
               'code': {
                   'git_repo': self.get_repo_url(),
                   'commit': self.get_commit_hash(),
                   'diff': self.get_uncommitted_diff(),
               },
               'data': {
                   'training_set': self.get_data_snapshot_id('train'),
                   'validation_set': self.get_data_snapshot_id('val'),
                   'preprocessing_version': self.get_pipeline_version(),
               },
               'environment': {
                   'docker_image': self.get_docker_image_digest(),
                   'pip_freeze': self.get_package_versions(),
                   'hardware': self.get_hardware_spec(),
               },
               'config': {
                   'hyperparameters': self.get_all_params(run_id),
                   'random_seeds': self.get_seeds(run_id),
               },
               'results': {
                   'final_metrics': self.get_final_metrics(run_id),
                   'model_checkpoints': self.get_checkpoint_urls(run_id),
               }
           }
       
       def reproduce(self, lineage_record):
           """Launch reproduction of an experiment."""
           # Checkout exact code version
           # Use exact data snapshot
           # Build exact environment (Docker)
           # Run with exact config + seeds
           pass
   ```

---

## Question 44: Data Pipeline for ML Training
**Difficulty: Staff Level | Topic: Data Engineering | Asked at: Databricks, Snowflake, Meta, Google**

Design a data pipeline that processes 100TB/day of raw data into ML-ready training datasets. Address data validation, schema evolution, deduplication, and ensuring data quality doesn't degrade model performance.

### Expected Answer:

**ML Data Pipeline Architecture:**

1. **Pipeline Overview:**
   ```
   Raw Sources          Processing              ML-Ready
   ┌─────────┐     ┌──────────────┐      ┌─────────────┐
   │ Events  │────▶│ Ingestion    │─────▶│ Bronze      │
   │ Logs    │     │ (Kafka/Kinesis)│     │ (Raw, append)│
   │ DB CDC  │     └──────────────┘      └──────┬──────┘
   │ APIs    │                                   │
   └─────────┘                                   ▼
                                          ┌─────────────┐
                                          │ Silver      │
                                          │ (Cleaned,   │
                                          │  validated) │
                                          └──────┬──────┘
                                                 │
                                                 ▼
                                          ┌─────────────┐
                                          │ Gold        │
                                          │ (Features,  │
                                          │  training   │
                                          │  datasets)  │
                                          └─────────────┘
   ```

2. **Data Validation Framework:**
   ```python
   class MLDataValidator:
       """Validate data quality before it reaches training."""
       
       def validate_batch(self, batch: DataFrame) -> ValidationReport:
           checks = []
           
           # Schema checks
           checks.append(self.check_schema(batch))
           
           # Statistical checks
           checks.append(self.check_distributions(batch))
           
           # ML-specific checks
           checks.append(self.check_label_distribution(batch))
           checks.append(self.check_feature_correlations(batch))
           checks.append(self.check_data_freshness(batch))
           
           # Anomaly detection
           checks.append(self.detect_data_anomalies(batch))
           
           report = ValidationReport(checks)
           
           if report.has_critical_failures:
               self.quarantine_batch(batch)
               self.alert("Data quality gate FAILED - batch quarantined")
           
           return report
       
       def check_distributions(self, batch):
           """Detect distribution shift vs reference data."""
           reference_stats = self.load_reference_statistics()
           
           issues = []
           for column in batch.columns:
               current_stats = compute_statistics(batch[column])
               
               # KS test for numerical columns
               if is_numerical(column):
                   ks_stat, p_value = ks_test(
                       batch[column].sample(10000),
                       reference_stats[column].sample
                   )
                   if p_value < 0.01:
                       issues.append(f"Distribution shift in {column}: "
                                   f"KS={ks_stat:.3f}, p={p_value:.4f}")
               
               # Null rate monitoring
               null_rate = batch[column].isnull().mean()
               expected_null_rate = reference_stats[column].null_rate
               if null_rate > expected_null_rate * 2:
                   issues.append(f"Null rate spike in {column}: "
                               f"{null_rate:.1%} vs expected {expected_null_rate:.1%}")
           
           return CheckResult('distributions', issues)
       
       def check_label_distribution(self, batch):
           """Ensure label balance hasn't changed dramatically."""
           label_dist = batch['label'].value_counts(normalize=True)
           expected_dist = self.reference_label_distribution
           
           # Chi-squared test
           chi2, p_value = chi_squared_test(label_dist, expected_dist)
           
           if p_value < 0.01:
               return CheckResult('label_dist', 
                   [f"Label distribution shifted: {label_dist.to_dict()}"])
           return CheckResult('label_dist', [])
   ```

3. **Schema Evolution Handling:**
   ```python
   class SchemaEvolutionManager:
       """Handle schema changes without breaking ML pipelines."""
       
       def handle_schema_change(self, old_schema, new_schema):
           changes = self.diff_schemas(old_schema, new_schema)
           
           for change in changes:
               if change.type == 'column_added':
                   # Safe: backfill with default, add to feature candidates
                   self.backfill_column(change.column, default=change.default)
                   self.notify_feature_team(f"New column available: {change.column}")
               
               elif change.type == 'column_removed':
                   # DANGEROUS: Check if any model depends on this column
                   dependent_models = self.find_dependent_models(change.column)
                   if dependent_models:
                       self.block_change(
                           f"Cannot remove {change.column}: "
                           f"used by models: {dependent_models}"
                       )
                   else:
                       self.deprecate_column(change.column)
               
               elif change.type == 'type_changed':
                   # Validate cast compatibility
                   if self.is_safe_cast(change.old_type, change.new_type):
                       self.apply_cast(change.column, change.new_type)
                   else:
                       self.block_change(f"Unsafe type change: {change}")
               
               elif change.type == 'semantic_change':
                   # Same column, different meaning (e.g., currency changed)
                   # Most dangerous: silent model degradation
                   self.version_column(change.column)
                   self.alert_all_consumers(change)
   ```

4. **Deduplication at Scale:**
   ```python
   class ScalableDeduplication:
       """Dedup 100TB/day efficiently."""
       
       def dedup_exact(self, batch):
           """Exact dedup using hash-based approach."""
           # Compute content hash for each record
           batch['content_hash'] = batch.apply(
               lambda row: hash_record(row, exclude=['timestamp', 'ingest_id']),
               axis=1
           )
           
           # Check against bloom filter (probabilistic, fast)
           new_records = []
           for record in batch.itertuples():
               if not self.bloom_filter.might_contain(record.content_hash):
                   new_records.append(record)
                   self.bloom_filter.add(record.content_hash)
               else:
                   # Might be duplicate, verify in hash store
                   if not self.hash_store.contains(record.content_hash):
                       new_records.append(record)
                       self.hash_store.add(record.content_hash)
           
           return new_records
       
       def dedup_fuzzy(self, batch, threshold=0.95):
           """Near-duplicate detection for text/unstructured data."""
           # MinHash LSH for approximate matching
           signatures = self.compute_minhash_signatures(batch)
           
           # LSH banding for candidate pairs
           candidates = self.lsh_index.query_batch(signatures)
           
           # Verify candidates with exact similarity
           duplicates = set()
           for id_a, id_b in candidates:
               sim = self.compute_similarity(batch[id_a], batch[id_b])
               if sim > threshold:
                   # Keep the newer record
                   duplicates.add(id_a if batch[id_a].ts < batch[id_b].ts else id_b)
           
           return batch.drop(duplicates)
   ```

5. **Training Dataset Versioning:**
   ```python
   class DatasetVersionManager:
       """Version datasets for reproducibility and rollback."""
       
       def create_version(self, dataset_name, query, description):
           """Create an immutable snapshot of a training dataset."""
           version = DatasetVersion(
               name=dataset_name,
               version_id=generate_version_id(),
               query=query,  # The SQL/transformation that defines this dataset
               created_at=time.time(),
               row_count=self.count_rows(query),
               schema=self.infer_schema(query),
               statistics=self.compute_statistics(query),
               lineage={
                   'source_tables': self.extract_source_tables(query),
                   'transforms': self.extract_transforms(query),
                   'filters': self.extract_filters(query),
               },
               storage_path=f's3://datasets/{dataset_name}/{version_id}/',
           )
           
           # Materialize (for reproducibility + performance)
           self.materialize(query, version.storage_path)
           
           # Register
           self.registry.register(version)
           
           return version
       
       def compare_versions(self, v1_id, v2_id):
           """Understand what changed between dataset versions."""
           v1 = self.registry.get(v1_id)
           v2 = self.registry.get(v2_id)
           
           return {
               'row_count_diff': v2.row_count - v1.row_count,
               'schema_changes': diff_schemas(v1.schema, v2.schema),
               'stat_changes': diff_statistics(v1.statistics, v2.statistics),
               'query_diff': diff_queries(v1.query, v2.query),
           }
   ```

---

## Question 45: Online Learning and Model Updates
**Difficulty: Staff Level | Topic: ML Systems | Asked at: Twitter/X, TikTok, Pinterest, Spotify**

Design a system for online/continual learning where models update in near-real-time based on user feedback. Address concept drift detection, safe model updates, and preventing catastrophic forgetting. How do you handle adversarial feedback?

### Expected Answer:

**Online Learning System Architecture:**

1. **System Overview:**
   ```
   ┌──────────────────────────────────────────────────────┐
   │                  Online Learning Loop                  │
   │                                                        │
   │  User Action → Feature → Predict → Serve → Feedback  │
   │       ▲                                        │      │
   │       │                                        ▼      │
   │  ┌─────────┐    ┌───────────┐    ┌──────────────┐   │
   │  │ Updated  │◀───│  Trainer  │◀───│  Feedback    │   │
   │  │ Model    │    │  (Online) │    │  Collector   │   │
   │  └─────────┘    └───────────┘    └──────────────┘   │
   │                        │                              │
   │                        ▼                              │
   │               ┌─────────────────┐                    │
   │               │  Safety Checks  │                    │
   │               │  (Before deploy)│                    │
   │               └─────────────────┘                    │
   └──────────────────────────────────────────────────────┘
   ```

2. **Concept Drift Detection:**
   ```python
   class ConceptDriftDetector:
       """Detect when data distribution or label relationship changes."""
       
       def __init__(self):
           self.detectors = {
               'feature_drift': ADWIN(),           # Adaptive windowing
               'prediction_drift': DDM(),          # Drift Detection Method
               'label_drift': PageHinkley(),       # Page-Hinkley test
               'performance_drift': KSWIN(),       # KS-window test
           }
       
       def update(self, features, prediction, label, timestamp):
           """Called for every labeled example."""
           # Feature drift: Are inputs changing?
           for i, feat_value in enumerate(features):
               self.detectors['feature_drift'].update(feat_value)
           
           # Prediction drift: Is model output distribution changing?
           self.detectors['prediction_drift'].update(prediction)
           
           # Performance drift: Is model accuracy degrading?
           error = int(prediction != label)
           self.detectors['performance_drift'].update(error)
           
           # Check all detectors
           alerts = {}
           for name, detector in self.detectors.items():
               if detector.detected_change():
                   alerts[name] = {
                       'type': name,
                       'severity': detector.get_severity(),
                       'timestamp': timestamp,
                       'window_stats': detector.get_stats(),
                   }
           
           if alerts:
               self.handle_drift(alerts)
       
       def handle_drift(self, alerts):
           """Response strategy based on drift type and severity."""
           if 'performance_drift' in alerts:
               severity = alerts['performance_drift']['severity']
               
               if severity == 'critical':  # >10% accuracy drop
                   # Immediate action: trigger full retrain
                   self.trigger_retrain(mode='full', priority='urgent')
               elif severity == 'warning':  # 3-10% drop
                   # Accelerate online learning rate
                   self.increase_learning_rate(factor=2.0)
                   self.expand_training_window()
               else:  # Gradual drift
                   # Normal online learning handles this
                   self.log_drift(alerts)
   ```

3. **Safe Online Update Strategy:**
   ```python
   class SafeOnlineUpdater:
       """Update model online while preventing catastrophic failures."""
       
       def __init__(self, base_model):
           self.production_model = base_model
           self.shadow_model = copy.deepcopy(base_model)  # Updated online
           self.validation_buffer = CircularBuffer(size=10000)
       
       def update(self, examples_batch):
           """Update shadow model, validate, then promote."""
           # Update shadow model with new examples
           self.shadow_model.partial_fit(
               examples_batch.features,
               examples_batch.labels,
               learning_rate=self.adaptive_lr()
           )
           
           # Validate against holdout buffer
           val_metrics = self.validate(self.shadow_model, self.validation_buffer)
           prod_metrics = self.validate(self.production_model, self.validation_buffer)
           
           # Promote only if shadow is better (or not significantly worse)
           if val_metrics.accuracy >= prod_metrics.accuracy - 0.005:
               self.promote_shadow_to_production()
           else:
               # Rollback shadow to production state
               self.shadow_model = copy.deepcopy(self.production_model)
               self.log_rejected_update(val_metrics, prod_metrics)
       
       def adaptive_lr(self):
           """Reduce learning rate over time to prevent oscillation."""
           updates_today = self.get_update_count_today()
           base_lr = 0.001
           # Decay: lr = base_lr / (1 + updates/100)
           return base_lr / (1 + updates_today / 100)
       
       def prevent_catastrophic_forgetting(self, new_examples):
           """Mix new examples with replay buffer of historical examples."""
           replay_examples = self.replay_buffer.sample(
               n=len(new_examples) * 3  # 3:1 replay ratio
           )
           mixed_batch = concatenate([new_examples, replay_examples])
           return shuffle(mixed_batch)
   ```

4. **Adversarial Feedback Protection:**
   ```python
   class AdversarialFeedbackFilter:
       """
       Prevent malicious users from poisoning the model through
       coordinated false feedback.
       """
       
       def filter_feedback(self, feedback_batch):
           clean_feedback = []
           
           for feedback in feedback_batch:
               # Check 1: Rate limiting per user
               if self.user_rate_exceeded(feedback.user_id):
                   continue
               
               # Check 2: Consistency check (does this user's feedback
               # match their behavioral signals?)
               if not self.is_consistent(feedback):
                   self.flag_suspicious(feedback)
                   continue
               
               # Check 3: Anomaly detection (is this feedback an outlier
               # compared to other users on same item?)
               if self.is_anomalous_feedback(feedback):
                   self.quarantine(feedback)
                   continue
               
               # Check 4: Source credibility (user trust score)
               if self.get_user_trust_score(feedback.user_id) < 0.3:
                   # Weight this feedback lower, don't exclude
                   feedback.weight = 0.1
               
               clean_feedback.append(feedback)
           
           # Check 5: Batch-level anomaly
           # If >20% of batch is from same IP/region/pattern → suspicious
           if self.detect_coordinated_attack(clean_feedback):
               self.alert("Possible coordinated feedback attack")
               return []  # Reject entire batch
           
           return clean_feedback
       
       def is_consistent(self, feedback):
           """Check if explicit feedback matches implicit signals."""
           # Example: User says "not relevant" but spent 5 minutes reading
           implicit_signal = self.get_implicit_signal(
               feedback.user_id, feedback.item_id
           )
           explicit_signal = feedback.label
           
           # If strong disagreement, flag
           if implicit_signal > 0.8 and explicit_signal < 0.2:
               return False
           return True
   ```

5. **A/B Testing for Online Learning Variants:**
   ```python
   class OnlineLearningExperiment:
       """Compare different online learning strategies."""
       
       def __init__(self):
           self.variants = {
               'control': {
                   'model': StaticModel(),  # No online updates
                   'traffic': 0.2,
               },
               'slow_update': {
                   'model': OnlineModel(update_freq='hourly'),
                   'traffic': 0.3,
               },
               'fast_update': {
                   'model': OnlineModel(update_freq='5min'),
                   'traffic': 0.3,
               },
               'continuous': {
                   'model': OnlineModel(update_freq='per_batch'),
                   'traffic': 0.2,
               },
           }
       
       def evaluate(self, window='7d'):
           results = {}
           for variant_name, config in self.variants.items():
               results[variant_name] = {
                   'ctr': self.compute_ctr(variant_name, window),
                   'revenue': self.compute_revenue(variant_name, window),
                   'latency': self.compute_latency(variant_name, window),
                   'model_stability': self.compute_prediction_variance(variant_name),
                   'drift_response_time': self.measure_adaptation_speed(variant_name),
               }
           return results
   ```
