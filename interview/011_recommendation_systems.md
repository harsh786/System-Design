# Large-Scale Recommendation Systems - Staff Architect Interview

## Question 51: Two-Tower Architecture at Scale
**Difficulty: Staff Level | Topic: RecSys Architecture | Asked at: Meta, Google, TikTok, Netflix**

Design a two-tower recommendation system that serves 1B users and 100M items with sub-50ms latency. Explain the training methodology, negative sampling strategies, and how to handle the cold-start problem for new users and items.

### Expected Answer:

**Two-Tower Recommendation Architecture:**

1. **Architecture Overview:**
   ```
   ┌──────────────┐              ┌──────────────┐
   │  User Tower   │              │  Item Tower   │
   │              │              │              │
   │  User features│              │ Item features │
   │  - Demographics│             │ - Content     │
   │  - History    │              │ - Metadata    │
   │  - Context    │              │ - Popularity  │
   │       │       │              │       │       │
   │  Dense Layers │              │  Dense Layers │
   │       │       │              │       │       │
   │  User Embedding│             │ Item Embedding│
   │   (256-dim)    │             │  (256-dim)    │
   └───────┬───────┘              └───────┬───────┘
           │                              │
           └──────── dot product ─────────┘
                         │
                    Relevance Score
   
   Key: Towers are INDEPENDENT at inference time.
   Item embeddings pre-computed and indexed in ANN.
   Only user tower runs at request time → fast!
   ```

2. **Training with Hard Negative Mining:**
   ```python
   class TwoTowerTrainer:
       def __init__(self, user_tower, item_tower):
           self.user_tower = user_tower
           self.item_tower = item_tower
       
       def train_step(self, batch):
           """
           Batch: (user_features, positive_item, hard_negatives, random_negatives)
           """
           # Compute embeddings
           user_emb = self.user_tower(batch.user_features)      # [B, 256]
           pos_emb = self.item_tower(batch.positive_items)      # [B, 256]
           neg_emb = self.item_tower(batch.negative_items)      # [B, N, 256]
           
           # In-batch negatives (free! other positives become negatives)
           # This gives B additional negatives per example
           all_pos_emb = pos_emb  # [B, 256]
           in_batch_scores = torch.matmul(user_emb, all_pos_emb.T)  # [B, B]
           
           # Positive scores (diagonal)
           pos_scores = (user_emb * pos_emb).sum(dim=-1)  # [B]
           
           # Hard negative scores
           hard_neg_scores = torch.bmm(
               neg_emb, user_emb.unsqueeze(-1)
           ).squeeze(-1)  # [B, N]
           
           # Sampled softmax loss
           logits = torch.cat([pos_scores.unsqueeze(1), hard_neg_scores], dim=1)
           labels = torch.zeros(batch_size, dtype=torch.long)  # positive is index 0
           
           loss = F.cross_entropy(logits / self.temperature, labels)
           
           # Correction for sampling bias
           # Popular items appear more as negatives → need log-correction
           loss -= self.log_correction(batch.negative_items)
           
           return loss
       
       def mine_hard_negatives(self, user_emb, positive_item_id):
           """
           Hard negatives: Items close in embedding space but NOT relevant.
           Much more informative than random negatives.
           """
           # Strategy 1: ANN search for nearest items that aren't positive
           candidates = self.ann_index.search(user_emb, top_k=200)
           hard_negs = [c for c in candidates if c.id != positive_item_id][:10]
           
           # Strategy 2: Items the user saw but didn't engage with (impressions)
           impression_negs = self.get_unclicked_impressions(user_id, limit=5)
           
           # Strategy 3: Mix of hard + random (prevents collapse)
           random_negs = self.sample_random_items(n=5)
           
           return hard_negs + impression_negs + random_negs
   ```

3. **Cold-Start Solutions:**
   ```python
   class ColdStartHandler:
       """Handle new users (no history) and new items (no interactions)."""
       
       def get_user_embedding_cold_start(self, user):
           if user.interaction_count == 0:
               # Pure cold start: Use content-based features only
               features = {
                   'demographics': user.age_bucket, user.gender, user.location,
                   'signup_context': user.referral_source, user.device_type,
                   'declared_interests': user.onboarding_selections,
               }
               return self.user_tower.forward(features)
           
           elif user.interaction_count < 10:
               # Warm start: Blend content features + limited history
               content_emb = self.user_tower.content_only(user.features)
               history_emb = self.user_tower.history_only(user.interactions)
               
               # Confidence-weighted blend
               alpha = min(user.interaction_count / 10, 1.0)
               return (1 - alpha) * content_emb + alpha * history_emb
           
           else:
               # Standard: Full user tower
               return self.user_tower(user.all_features)
       
       def get_item_embedding_cold_start(self, item):
           if item.interaction_count == 0:
               # New item: Use content features (title, description, image)
               content_emb = self.item_tower.content_only({
                   'text_embedding': self.text_encoder(item.title + item.description),
                   'image_embedding': self.image_encoder(item.thumbnail),
                   'category': item.category,
                   'creator_features': item.creator_embedding,
               })
               return content_emb
           else:
               return self.item_tower(item.all_features)
       
       def exploration_strategy(self, user, candidates):
           """Boost new items to collect interactions (explore-exploit)."""
           scores = []
           for item in candidates:
               base_score = self.predict(user, item)
               
               # Exploration bonus for new items
               uncertainty = 1.0 / (1 + math.log1p(item.interaction_count))
               exploration_bonus = self.epsilon * uncertainty
               
               scores.append(base_score + exploration_bonus)
           
           return scores
   ```

4. **Serving Architecture (Sub-50ms):**
   ```python
   class RecommendationServingPipeline:
       """
       Latency budget:
       - User tower inference: 5ms
       - ANN retrieval: 10ms
       - Feature fetch: 10ms (parallel with above)
       - Ranking model: 15ms
       - Business logic: 5ms
       - Network: 5ms
       Total: ~50ms
       """
       
       def serve(self, user_id, context):
           # Pre-computed: All item embeddings indexed in ANN (updated hourly)
           
           # Step 1: Fetch user features + compute user embedding
           user_features = self.feature_store.get(user_id)  # <5ms (Redis)
           user_emb = self.user_tower.infer(user_features)  # <5ms (optimized)
           
           # Step 2: Retrieve candidates via ANN
           candidates = self.ann_index.search(user_emb, top_k=500)  # <10ms
           
           # Step 3: Lightweight re-ranking (cross-features)
           # Use a small ranking model that considers user×item interactions
           ranked = self.ranker.score(user_features, candidates)  # <15ms
           
           # Step 4: Business rules & diversity
           final = self.apply_business_rules(ranked[:100])
           final = self.diversify(final, top_k=20)
           
           return final
       
       def update_item_index(self):
           """Batch job: Recompute all item embeddings and rebuild ANN index."""
           # Run hourly (or when new items arrive)
           all_items = self.item_store.get_all_active_items()
           
           embeddings = self.item_tower.batch_infer(all_items)  # GPU batch
           
           # Build new ANN index
           new_index = HNSWIndex(dim=256, M=32, ef_construction=400)
           new_index.add(embeddings, ids=[item.id for item in all_items])
           
           # Atomic swap
           self.ann_index = new_index
   ```

5. **Multi-Objective Optimization:**
   ```python
   class MultiObjectiveRecommender:
       """
       Real systems optimize multiple objectives simultaneously:
       engagement, revenue, diversity, freshness, creator fairness.
       """
       
       def score(self, user, item):
           # Multiple prediction heads from shared backbone
           engagement_score = self.engagement_head(user, item)  # P(click)
           watch_time_score = self.watch_time_head(user, item)  # E[watch_time]
           share_score = self.share_head(user, item)           # P(share)
           revenue_score = self.revenue_head(user, item)       # E[revenue]
           
           # Scalarization with tunable weights
           # Weights tuned via online experiments
           final_score = (
               self.w_engagement * engagement_score +
               self.w_watch_time * watch_time_score +
               self.w_share * share_score * 2.0 +  # Shares valued more
               self.w_revenue * revenue_score
           )
           
           # Diversity penalty (MMR-style)
           similarity_to_shown = self.compute_similarity_to_slate(item)
           final_score -= self.diversity_weight * similarity_to_shown
           
           # Freshness boost
           age_hours = (time.time() - item.created_at) / 3600
           freshness_boost = 1.0 / (1 + age_hours / 24)
           final_score += self.freshness_weight * freshness_boost
           
           return final_score
   ```

---

## Question 52: Real-Time Feature Engineering for Recommendations
**Difficulty: Staff Level | Topic: Feature Engineering | Asked at: TikTok, Pinterest, Spotify, Uber**

Design a real-time feature computation system that generates user behavioral features (last 5 minutes of activity) for a recommendation model serving 500K requests/second. Features include: session click count, category distribution, real-time engagement signals.

### Expected Answer:

**Real-Time Feature System:**

1. **Architecture:**
   ```
   ┌──────────────────────────────────────────────────────────┐
   │                Real-Time Feature Pipeline                  │
   │                                                            │
   │  Events → Kafka → Flink/Spark Streaming → Feature Store   │
   │                                                            │
   │  ┌──────────┐    ┌──────────────┐    ┌────────────┐      │
   │  │ Click    │───▶│ Stream       │───▶│ Redis      │      │
   │  │ Impression│   │ Processor    │    │ (Online)   │      │
   │  │ Purchase │    │ (Windows:    │    │            │      │
   │  │ View     │    │  1m,5m,1h)   │    │ p99 < 2ms │      │
   │  └──────────┘    └──────────────┘    └────────────┘      │
   │                                                            │
   │  Model Server reads features from Redis at request time    │
   └──────────────────────────────────────────────────────────┘
   ```

2. **Streaming Feature Computation:**
   ```python
   class RealTimeFeatureProcessor:
       """
       Compute windowed aggregates from event stream.
       Challenge: 500K reads/sec + 1M events/sec.
       """
       
       def __init__(self):
           self.windows = ['1min', '5min', '30min', '1hr', '24hr']
           self.redis = RedisCluster(nodes=50)  # Sharded Redis
       
       def process_event(self, event):
           """Called for every user action (click, view, purchase)."""
           user_id = event['user_id']
           timestamp = event['timestamp']
           
           # Feature 1: Action counts per window
           for window in self.windows:
               key = f"count:{event['action']}:{user_id}:{window}"
               self.redis.incr(key)
               self.redis.expire(key, window_to_seconds(window))
           
           # Feature 2: Category distribution (what categories user browsed)
           if 'category' in event:
               cat_key = f"cat_dist:{user_id}:5min"
               self.redis.hincrby(cat_key, event['category'], 1)
               self.redis.expire(cat_key, 300)
           
           # Feature 3: Session engagement metrics
           session_key = f"session:{user_id}"
           self.redis.hset(session_key, mapping={
               'last_action_ts': timestamp,
               'action_count': self.redis.hincrby(session_key, 'action_count', 1),
               'last_category': event.get('category', ''),
               'engagement_time': self.compute_engagement_delta(user_id, timestamp),
           })
           self.redis.expire(session_key, 1800)  # 30min session timeout
           
           # Feature 4: Real-time sequence (last N items interacted)
           seq_key = f"seq:{user_id}"
           self.redis.lpush(seq_key, event.get('item_id', ''))
           self.redis.ltrim(seq_key, 0, 49)  # Keep last 50
           self.redis.expire(seq_key, 86400)
       
       def get_features(self, user_id) -> dict:
           """Called at prediction time. Must be < 2ms."""
           pipe = self.redis.pipeline()
           
           # Batch all feature reads in one round-trip
           pipe.get(f"count:click:{user_id}:5min")
           pipe.get(f"count:click:{user_id}:1hr")
           pipe.hgetall(f"cat_dist:{user_id}:5min")
           pipe.hgetall(f"session:{user_id}")
           pipe.lrange(f"seq:{user_id}", 0, 9)  # Last 10 items
           
           results = pipe.execute()
           
           return {
               'click_count_5min': int(results[0] or 0),
               'click_count_1hr': int(results[1] or 0),
               'category_distribution': self.normalize_dict(results[2]),
               'session_features': results[3],
               'recent_items': results[4],
           }
   ```

3. **Handling Late Events and Ordering:**
   ```python
   class EventOrderingHandler:
       """
       Challenge: Events arrive out-of-order due to network delays.
       Solution: Event-time processing with watermarks.
       """
       
       def __init__(self, max_lateness=timedelta(seconds=30)):
           self.max_lateness = max_lateness
           self.watermark = None
           self.late_event_buffer = {}
       
       def process_with_ordering(self, event):
           event_time = event['timestamp']
           
           if self.watermark and event_time < self.watermark - self.max_lateness:
               # Too late - drop or send to dead-letter queue
               self.metrics.increment('dropped_late_events')
               return
           
           if self.watermark and event_time < self.watermark:
               # Late but within tolerance - process with correction
               self.apply_late_correction(event)
           else:
               # On-time event
               self.process_event(event)
           
           # Advance watermark
           self.watermark = max(self.watermark or event_time, 
                               event_time - self.max_lateness)
       
       def apply_late_correction(self, event):
           """Correct window aggregates for late-arriving events."""
           user_id = event['user_id']
           
           # Which windows does this event belong to?
           for window in self.windows:
               window_start, window_end = self.get_window_bounds(
                   event['timestamp'], window
               )
               if time.time() < window_end:
                   # Window still active - just add the event
                   self.process_event(event)
               # If window closed, this event is lost (acceptable trade-off)
   ```

4. **Feature Consistency (Training = Serving):**
   ```python
   class FeatureConsistencyGuarantee:
       """
       Critical: Features used in training MUST match features at serving time.
       Common pitfall: Training uses batch-computed features,
       serving uses real-time computed features → different values!
       """
       
       def log_serving_features(self, user_id, features, prediction_id):
           """Log features exactly as served for training data generation."""
           # This becomes the source of truth for training
           self.feature_log.write({
               'prediction_id': prediction_id,
               'user_id': user_id,
               'features': features,  # Exact values used at inference
               'timestamp': time.time(),
           })
       
       def generate_training_data(self):
           """
           Join: logged features + delayed labels.
           This guarantees training sees the SAME features as serving.
           """
           # features_log JOIN outcomes ON prediction_id
           training_data = self.join_features_and_labels(
               features_table='feature_log',
               labels_table='outcomes',
               join_key='prediction_id'
           )
           return training_data
       
       def validate_consistency(self):
           """Periodically check that online features match offline computation."""
           sample_users = self.sample_active_users(n=1000)
           
           for user_id in sample_users:
               online_features = self.online_store.get_features(user_id)
               offline_features = self.offline_compute.get_features(user_id)
               
               for feature_name in online_features:
                   online_val = online_features[feature_name]
                   offline_val = offline_features.get(feature_name)
                   
                   if not self.approximately_equal(online_val, offline_val, rtol=0.05):
                       self.log_inconsistency(user_id, feature_name, 
                                            online_val, offline_val)
   ```

5. **Scaling to 500K Requests/Second:**
   ```
   Architecture decisions:
   
   Redis cluster: 50 nodes (10K reads/sec per node × 50 = 500K)
   - Sharded by user_id (consistent hashing)
   - Read replicas: 3 per primary (handle read spikes)
   - Memory: ~100GB per node (2M users × 50 features × 1KB)
   
   Event processing: Flink cluster
   - 100 task slots
   - Processing 1M events/sec
   - Event-time windows with 30s watermark
   - Exactly-once semantics (Kafka transactions)
   
   Feature serving optimization:
   - Batch feature reads (pipeline multiple keys in single Redis call)
   - Local cache (LRU, 10s TTL) for very active users
   - Feature pre-computation during idle periods
   - Fallback to default features if Redis timeout (graceful degradation)
   
   Monitoring:
   - Redis latency p99 < 2ms (alert at 5ms)
   - Feature staleness < 10s for 99% of requests
   - Event processing lag < 5s
   - Feature computation throughput > 1.2M events/sec (headroom)
   ```

---

## Question 53: Ranking Model Architecture (Learning to Rank)
**Difficulty: Staff Level | Topic: ML Architecture | Asked at: Google, Meta, LinkedIn, Amazon**

Design a multi-stage ranking system for a feed/search product. Explain the trade-offs between pointwise, pairwise, and listwise loss functions. How do you handle position bias in training data? Design the full stack from candidate generation to final ranking.

### Expected Answer:

**Multi-Stage Ranking System:**

1. **Funnel Architecture:**
   ```
   ┌─────────────────────────────────────────┐
   │ Stage 0: Candidate Generation            │
   │ Input: Full corpus (100M items)          │
   │ Output: ~10,000 candidates               │
   │ Method: Two-tower ANN, inverted index    │
   │ Latency: 10ms                            │
   │ Model: Simple (embedding similarity)     │
   ├─────────────────────────────────────────┤
   │ Stage 1: Pre-Ranking (Light Ranker)      │
   │ Input: 10,000 candidates                 │
   │ Output: 500 candidates                   │
   │ Method: Small neural net, limited features│
   │ Latency: 10ms                            │
   │ Model: 2-layer MLP, 50 features          │
   ├─────────────────────────────────────────┤
   │ Stage 2: Full Ranking (Heavy Ranker)     │
   │ Input: 500 candidates                    │
   │ Output: 50 ranked items                  │
   │ Method: Deep model, all features, cross  │
   │ Latency: 20ms                            │
   │ Model: DCN-v2, 500+ features             │
   ├─────────────────────────────────────────┤
   │ Stage 3: Re-Ranking (Policy Layer)       │
   │ Input: 50 items                          │
   │ Output: Final 20 items (page 1)          │
   │ Method: Business rules, diversity, ads   │
   │ Latency: 5ms                             │
   └─────────────────────────────────────────┘
   ```

2. **Loss Functions Comparison:**
   ```python
   class RankingLossFunctions:
       
       def pointwise_loss(self, predictions, labels):
           """
           Treat each item independently.
           + Simple, easy to train
           - Doesn't optimize ranking directly
           - Calibrated but not rank-optimal
           """
           return F.binary_cross_entropy(predictions, labels)
       
       def pairwise_loss(self, pos_scores, neg_scores, margin=1.0):
           """
           BPR Loss: Optimize relative ordering of pairs.
           + Directly optimizes ranking
           - O(n²) pairs, sampling needed
           - Doesn't consider full list context
           """
           diff = pos_scores - neg_scores
           return -torch.log(torch.sigmoid(diff)).mean()
       
       def listwise_loss(self, scores, relevance_labels):
           """
           ListNet/LambdaRank: Optimize entire ranked list.
           + Best ranking quality
           + Considers list-level metrics (NDCG)
           - Complex, harder to train
           - Requires full list context
           """
           # LambdaRank: Weight gradients by NDCG delta
           sorted_indices = torch.argsort(scores, descending=True)
           
           lambda_weights = []
           for i in range(len(scores)):
               for j in range(i+1, len(scores)):
                   if relevance_labels[i] != relevance_labels[j]:
                       # NDCG gain from swapping positions i and j
                       ndcg_delta = abs(
                           self.dcg_gain(relevance_labels[i], sorted_indices[i]) -
                           self.dcg_gain(relevance_labels[i], sorted_indices[j])
                       )
                       lambda_weights.append(ndcg_delta)
           
           # Weight the pairwise loss by NDCG impact
           return weighted_pairwise_loss(scores, relevance_labels, lambda_weights)
       
       def recommendation(self):
           """When to use what:
           - Pointwise: Initial model, when calibration matters (bid prediction)
           - Pairwise: Mid-stage ranker, good balance of quality and simplicity
           - Listwise: Final ranker, when NDCG/MAP is the optimization target
           - Multi-task: Production systems (pointwise for each objective, 
                         listwise for final combined score)
           """
           pass
   ```

3. **Position Bias Correction:**
   ```python
   class PositionBiasCorrector:
       """
       Problem: Users click top results more regardless of relevance.
       Training on click data without correction learns position bias.
       """
       
       def inverse_propensity_weighting(self, clicks, positions):
           """
           Weight examples by inverse of position examination probability.
           Items shown at position 1 get weight 1/P(examine|pos=1).
           """
           # Estimate examination probability per position
           # Method: Randomized experiment or regression-based estimation
           exam_probs = self.estimate_examination_probability()
           # Typical: pos 1 = 1.0, pos 2 = 0.8, pos 5 = 0.4, pos 10 = 0.1
           
           # Weight positive examples by inverse propensity
           weights = []
           for click, position in zip(clicks, positions):
               if click:
                   weights.append(1.0 / exam_probs[position])
               else:
                   # Unclicked: could be unexamined OR examined-but-not-relevant
                   # Don't upweight negatives (they're noisy)
                   weights.append(1.0)
           
           return weights
       
       def position_as_feature(self, model):
           """
           Include position as input feature during training.
           At inference: Set position to a default value (e.g., 0 or mean).
           This lets the model LEARN the position effect and separate it.
           """
           # Training: model(features, position) → prediction
           # Serving: model(features, position=0) → unbiased prediction
           pass
       
       def counterfactual_training(self, logs):
           """
           Use randomized data for unbiased evaluation.
           Periodically serve random results to small % of traffic.
           This data has no position bias (random position assignment).
           """
           # 1% of traffic gets randomized results
           random_logs = logs[logs['is_randomized'] == True]
           
           # Train on random data (unbiased but small)
           # + use as validation for models trained on biased data
           return random_logs
   ```

4. **Deep Cross Network v2 (Production Ranker):**
   ```python
   class DCNv2Ranker(nn.Module):
       """
       State-of-the-art production ranking model.
       Captures explicit feature crosses at multiple orders.
       """
       
       def __init__(self, feature_dims, cross_layers=3, deep_layers=[512, 256, 128]):
           super().__init__()
           
           # Embedding layers for categorical features
           self.embeddings = nn.ModuleDict({
               name: nn.Embedding(dim, 64) for name, dim in feature_dims.items()
           })
           
           # Cross network (explicit feature interactions)
           input_dim = sum(64 for _ in feature_dims) + len(dense_features)
           self.cross_layers = nn.ModuleList([
               CrossLayer(input_dim) for _ in range(cross_layers)
           ])
           
           # Deep network (implicit patterns)
           layers = []
           prev_dim = input_dim
           for dim in deep_layers:
               layers.extend([nn.Linear(prev_dim, dim), nn.ReLU(), nn.Dropout(0.1)])
               prev_dim = dim
           self.deep_network = nn.Sequential(*layers)
           
           # Combine cross + deep
           self.output_layer = nn.Linear(input_dim + deep_layers[-1], 1)
       
       def forward(self, features):
           # Embed categorical features
           embedded = [self.embeddings[name](features[name]) 
                      for name in self.embeddings]
           x = torch.cat(embedded + [features['dense']], dim=-1)
           
           # Cross network
           x_cross = x
           for cross_layer in self.cross_layers:
               x_cross = cross_layer(x, x_cross)  # x0 * (W * x_l + b) + x_l
           
           # Deep network
           x_deep = self.deep_network(x)
           
           # Combine
           combined = torch.cat([x_cross, x_deep], dim=-1)
           output = torch.sigmoid(self.output_layer(combined))
           
           return output
   ```

5. **Online Metric Evaluation:**
   ```python
   class RankingMetrics:
       """Production metrics for ranking quality."""
       
       def compute_online_metrics(self, impressions, interactions):
           return {
               # Engagement metrics
               'ctr': interactions.clicks / impressions.total,
               'engagement_rate': interactions.engagements / impressions.total,
               'time_spent_per_session': interactions.total_time / sessions,
               
               # Ranking quality metrics
               'mrr': self.mean_reciprocal_rank(interactions),
               'ndcg@10': self.ndcg(interactions, k=10),
               
               # Diversity metrics
               'coverage': len(shown_items.unique()) / total_items,
               'intra_list_diversity': self.avg_pairwise_distance(shown_lists),
               
               # Fairness metrics
               'supplier_gini': self.gini_coefficient(item_impressions),
               'position_fairness': self.position_equality(groups),
               
               # Business metrics
               'revenue_per_1000_impressions': revenue / (impressions.total / 1000),
               'conversion_rate': purchases / impressions.total,
           }
       
       def detect_ranking_degradation(self, current_metrics, baseline_metrics):
           """Statistical test for ranking quality changes."""
           for metric_name in ['ndcg@10', 'ctr', 'time_spent']:
               t_stat, p_value = ttest_ind(
                   current_metrics[metric_name],
                   baseline_metrics[metric_name]
               )
               if p_value < 0.01 and current_metrics[metric_name].mean() < baseline_metrics[metric_name].mean():
                   self.alert(f"Ranking degradation: {metric_name} "
                            f"dropped from {baseline_metrics[metric_name].mean():.4f} "
                            f"to {current_metrics[metric_name].mean():.4f}")
   ```

---

## Question 54: Embedding-Based Retrieval at Internet Scale
**Difficulty: Staff Level | Topic: Information Retrieval | Asked at: Google, Meta, Spotify, Airbnb**

Design an embedding-based retrieval system for a search product with 10B documents. How do you train embeddings that capture semantic relevance? How do you handle the freshness problem (new documents)? Design the full pipeline from embedding training to serving.

### Expected Answer:

**Internet-Scale Embedding Retrieval:**

1. **Embedding Training Pipeline:**
   ```python
   class SearchEmbeddingTrainer:
       """
       Train query and document embeddings for semantic search.
       Key challenge: Learning good representations from noisy click data.
       """
       
       def __init__(self):
           self.query_encoder = TransformerEncoder(layers=6, dim=768)
           self.doc_encoder = TransformerEncoder(layers=12, dim=768)
           self.projection = nn.Linear(768, 256)  # Reduce for serving efficiency
       
       def prepare_training_data(self):
           """
           Data sources (ordered by quality):
           1. Human relevance judgments (expensive, high quality, small)
           2. Click data with dwell time (large, noisy)
           3. Query reformulations (implicit relevance signal)
           4. Hard negative mining (critical for quality)
           """
           positives = []
           
           # Clicked results with >30s dwell time → relevant
           positives += self.get_dwell_time_positives(min_dwell=30)
           
           # Query→Click→Query chains (reformulation = same intent)
           positives += self.get_reformulation_positives()
           
           # Human labels (gold standard, use for validation)
           validation = self.get_human_labels()
           
           return positives, validation
       
       def train_with_curriculum(self, data):
           """
           Curriculum: Easy negatives first, then gradually harder.
           Prevents model collapse in early training.
           """
           for epoch in range(self.num_epochs):
               # Phase 1: Random negatives (easy)
               if epoch < 3:
                   negatives = self.random_negatives(data, per_positive=7)
               
               # Phase 2: BM25 negatives (medium - lexically similar but irrelevant)
               elif epoch < 7:
                   negatives = self.bm25_negatives(data, per_positive=4)
                   negatives += self.random_negatives(data, per_positive=3)
               
               # Phase 3: Hard negatives from current model (hardest)
               else:
                   negatives = self.model_hard_negatives(data, per_positive=3)
                   negatives += self.bm25_negatives(data, per_positive=2)
                   negatives += self.random_negatives(data, per_positive=2)
               
               self.train_epoch(data, negatives)
   ```

2. **Freshness Solution:**
   ```python
   class FreshnessManager:
       """
       Challenge: 10B docs, new docs added every second.
       Can't re-embed everything (would take days).
       """
       
       def __init__(self):
           self.main_index = HNSWIndex(size='10B')  # Rebuilt weekly
           self.fresh_index = HNSWIndex(size='10M')  # Rebuilt hourly
           self.realtime_buffer = BruteForceIndex(size='100K')  # Last 5 min
       
       def ingest_new_document(self, doc):
           """Process new document within seconds."""
           # Embed immediately
           embedding = self.doc_encoder.encode(doc)
           
           # Add to real-time buffer (brute force, small)
           self.realtime_buffer.add(doc.id, embedding)
           
           # Queue for batch indexing (next hourly rebuild)
           self.fresh_queue.push(doc.id, embedding)
       
       def search(self, query_embedding, top_k=10):
           """Search across all index tiers."""
           # Search each tier in parallel
           main_results = self.main_index.search(query_embedding, top_k=top_k)
           fresh_results = self.fresh_index.search(query_embedding, top_k=top_k)
           realtime_results = self.realtime_buffer.search(query_embedding, top_k=top_k)
           
           # Merge results
           all_results = main_results + fresh_results + realtime_results
           
           # Re-rank merged results
           return sorted(all_results, key=lambda x: x.score, reverse=True)[:top_k]
       
       def rebuild_schedule(self):
           """
           - Real-time buffer: Always current (brute force, <100K docs)
           - Fresh index: Rebuilt every hour (HNSW, <10M docs)
           - Main index: Rebuilt weekly (HNSW, 10B docs, takes 2 days)
           
           Staleness worst case:
           - New doc in real-time buffer: <5 seconds
           - Fresh index includes it: <1 hour
           - Main index includes it: <1 week
           """
           pass
   ```

3. **Serving at 10B Scale:**
   ```
   Infrastructure:
   
   10B documents × 256-dim × 4 bytes = 10TB embeddings
   + HNSW graph overhead: ~3TB
   Total: ~13TB
   
   Sharding strategy:
   - 500 shards × 20M docs each
   - Each shard: ~26GB (fits in RAM of a 64GB machine)
   - 3 replicas per shard = 1500 machines
   
   Query routing:
   - Coarse quantizer: 500 centroids (one per shard)
   - Query hits top-20 shards (4% of total)
   - Parallel search across 20 shards
   
   Latency budget:
   - Query encoding: 10ms (optimized transformer)
   - Centroid matching: 1ms
   - Network to shards: 2ms
   - HNSW search per shard: 5ms
   - Merge results: 2ms
   - Total: ~20ms ✓
   ```

4. **Quality Evaluation:**
   ```python
   class EmbeddingQualityEvaluator:
       def evaluate(self, model):
           """Comprehensive embedding quality assessment."""
           results = {}
           
           # Offline metrics (human-labeled test set)
           results['ndcg@10'] = self.eval_ndcg(model, self.test_set)
           results['recall@100'] = self.eval_recall(model, self.test_set, k=100)
           results['mrr'] = self.eval_mrr(model, self.test_set)
           
           # Embedding space quality
           results['embedding_uniformity'] = self.measure_uniformity(model)
           results['embedding_alignment'] = self.measure_alignment(model)
           
           # Retrieval-augmented evaluation
           # Does embedding retrieval find docs that BM25 misses (and vice versa)?
           results['complement_rate'] = self.measure_complementarity(
               model, self.bm25_baseline
           )
           
           # Failure analysis
           results['failure_categories'] = self.analyze_failures(
               model, self.test_set
           )
           # Common failures: synonyms, negation, numerical reasoning
           
           return results
   ```

5. **Hybrid Retrieval (Embeddings + Sparse):**
   ```python
   class HybridRetriever:
       """
       Best practice: Combine semantic embeddings with sparse retrieval.
       They have complementary strengths.
       
       Embeddings: Great at semantic matching, bad at exact/rare terms
       BM25/Sparse: Great at exact matching, bad at paraphrases
       """
       
       def search(self, query, top_k=10):
           # Semantic search
           query_emb = self.encode_query(query)
           semantic_results = self.vector_index.search(query_emb, top_k=100)
           
           # Sparse search (BM25 or learned sparse like SPLADE)
           sparse_results = self.sparse_index.search(query, top_k=100)
           
           # Fusion
           # Method 1: Reciprocal Rank Fusion (simple, robust)
           fused = self.rrf(semantic_results, sparse_results, k=60)
           
           # Method 2: Learned fusion (better but needs training)
           # fused = self.fusion_model.score(query, semantic_results, sparse_results)
           
           return fused[:top_k]
       
       def rrf(self, *result_lists, k=60):
           """Reciprocal Rank Fusion."""
           scores = defaultdict(float)
           for results in result_lists:
               for rank, (doc_id, _) in enumerate(results):
                   scores[doc_id] += 1.0 / (k + rank + 1)
           return sorted(scores.items(), key=lambda x: x[1], reverse=True)
   ```

---

## Question 55: Reinforcement Learning for Recommendations
**Difficulty: Staff Level | Topic: RL + RecSys | Asked at: YouTube, TikTok, Netflix, Spotify**

Compare bandit algorithms vs full RL for recommendation optimization. Design a system that optimizes for long-term user satisfaction rather than immediate clicks. How do you handle off-policy evaluation and safe deployment of RL policies?

### Expected Answer:

**RL-Based Recommendation System:**

1. **Why RL for Recommendations:**
   ```
   Supervised Learning (standard):
   - Optimizes: P(click | user, item)
   - Problem: Maximizes immediate engagement
   - Result: Clickbait, filter bubbles, user burnout
   
   Reinforcement Learning:
   - Optimizes: Long-term cumulative reward (user satisfaction over session/lifetime)
   - Considers: Future consequences of current recommendations
   - Result: Sustainable engagement, user retention
   
   Spectrum:
   Bandits ←─────────────────────────────→ Full RL
   (no state)                             (full MDP)
   Simple, fast                           Complex, powerful
   
   Contextual Bandits: Best starting point for most teams.
   Full RL: When you have clear sequential dynamics (music playlists, 
            learning paths, multi-turn conversation).
   ```

2. **Contextual Bandit System:**
   ```python
   class ContextualBanditRecommender:
       """
       Action: Select which items to show
       Context: User features + session state
       Reward: Engagement signal (not just clicks)
       
       Advantage over supervised: Handles exploration naturally.
       """
       
       def __init__(self):
           self.policy = NeuralLinearPolicy(
               feature_dim=256,
               num_arms=1000,  # Item clusters
               exploration='ucb'
           )
       
       def recommend(self, user_context):
           # Get estimated rewards and uncertainty for each arm
           estimated_rewards, uncertainties = self.policy.predict(user_context)
           
           # UCB (Upper Confidence Bound) for exploration
           ucb_scores = estimated_rewards + self.alpha * uncertainties
           
           # Select top-K items with highest UCB
           selected_arms = torch.topk(ucb_scores, k=20)
           
           # Map arms back to specific items
           items = self.get_items_for_arms(selected_arms)
           
           return items
       
       def update(self, context, action, reward):
           """Online update after observing reward."""
           # Reward definition (crucial!):
           # NOT just clicks. Composite reward:
           reward = self.compute_composite_reward(action)
           
           self.policy.update(context, action, reward)
       
       def compute_composite_reward(self, interaction):
           """
           Reward signal that captures long-term value.
           """
           reward = 0.0
           
           # Immediate signals
           reward += 0.1 * interaction.clicked
           reward += 0.3 * min(interaction.dwell_time / 60, 5)  # Cap at 5 min
           reward += 0.5 * interaction.completed  # Finished content
           reward += 1.0 * interaction.shared
           reward += 1.5 * interaction.saved
           
           # Negative signals
           reward -= 0.5 * interaction.reported
           reward -= 0.3 * interaction.hide_content
           reward -= 0.2 * interaction.back_button_quick  # <3 sec = regret
           
           # Long-term signals (delayed)
           reward += 2.0 * interaction.returned_next_day  # Retention signal
           
           return reward
   ```

3. **Off-Policy Evaluation (OPE):**
   ```python
   class OffPolicyEvaluator:
       """
       Critical: Evaluate new policy WITHOUT deploying it.
       Can't A/B test every policy change (too expensive/risky).
       """
       
       def evaluate_policy(self, new_policy, logged_data):
           """
           Logged data: (context, action_taken, reward, logging_policy_prob)
           New policy: π_new(action | context)
           
           Question: What reward would new_policy have gotten?
           """
           estimates = {}
           
           # Method 1: Inverse Propensity Scoring (IPS)
           estimates['ips'] = self.ips_estimate(new_policy, logged_data)
           
           # Method 2: Doubly Robust (DR) - combines IPS + direct method
           estimates['dr'] = self.doubly_robust_estimate(new_policy, logged_data)
           
           # Method 3: Direct Method (reward model)
           estimates['dm'] = self.direct_method_estimate(new_policy, logged_data)
           
           return estimates
       
       def ips_estimate(self, new_policy, logged_data):
           """Importance-weighted estimator."""
           weighted_rewards = []
           
           for context, action, reward, log_prob in logged_data:
               new_prob = new_policy.probability(action, context)
               
               # Importance weight: ratio of new vs old policy probabilities
               weight = new_prob / log_prob
               
               # Clip weights to reduce variance (SNIPS)
               weight = min(weight, self.clip_threshold)
               
               weighted_rewards.append(weight * reward)
           
           # Self-normalized IPS (more stable)
           return sum(weighted_rewards) / sum(weights)
       
       def confidence_interval(self, estimate, logged_data):
           """Bootstrap confidence interval for OPE estimate."""
           bootstrap_estimates = []
           for _ in range(1000):
               sample = random.choices(logged_data, k=len(logged_data))
               boot_est = self.ips_estimate(self.new_policy, sample)
               bootstrap_estimates.append(boot_est)
           
           return (np.percentile(bootstrap_estimates, 2.5),
                   np.percentile(bootstrap_estimates, 97.5))
   ```

4. **Safe RL Deployment:**
   ```python
   class SafeRLDeployer:
       """
       RL policies can be catastrophic if unconstrained.
       Safety mechanisms for production deployment.
       """
       
       def deploy_with_guardrails(self, rl_policy):
           # Guardrail 1: Action space constraints
           constrained_policy = ActionConstrainedPolicy(
               base_policy=rl_policy,
               constraints={
                   'min_diversity': 0.3,     # At least 30% diverse content
                   'max_repeat': 0.1,        # Max 10% repeated items in session
                   'freshness_floor': 0.2,   # At least 20% content < 7 days old
                   'quality_floor': 0.4,     # Min quality score for all items
               }
           )
           
           # Guardrail 2: Performance floor (fallback to baseline)
           safe_policy = PerformanceGuardedPolicy(
               main_policy=constrained_policy,
               fallback_policy=self.production_baseline,
               min_performance_ratio=0.95,  # Must be within 5% of baseline
               evaluation_window='1h'
           )
           
           # Guardrail 3: Gradual rollout
           deployment = GradualRollout(
               policy=safe_policy,
               schedule=[
                   (0.01, '2h'),    # 1% traffic for 2 hours
                   (0.05, '6h'),    # 5% for 6 hours
                   (0.20, '24h'),   # 20% for 1 day
                   (0.50, '48h'),   # 50% for 2 days
                   (1.00, None),    # Full rollout
               ],
               promotion_criteria={
                   'engagement_lift': '>= 0%',     # Not worse than baseline
                   'retention_neutral': '>= -1%',  # Retention not tanking
                   'no_safety_violations': True,
               }
           )
           
           return deployment
       
       def monitor_rl_policy(self, policy_name):
           """Real-time monitoring specific to RL policies."""
           metrics = {
               'exploration_rate': self.measure_exploration(policy_name),
               'action_entropy': self.measure_action_diversity(policy_name),
               'reward_trend': self.compute_reward_ema(policy_name),
               'user_satisfaction_proxy': self.compute_satisfaction(policy_name),
               'session_length_trend': self.compute_session_lengths(policy_name),
               
               # RL-specific concerns
               'reward_hacking_signal': self.detect_reward_hacking(policy_name),
               'diversity_collapse': self.detect_filter_bubble(policy_name),
               'engagement_sustainability': self.measure_long_term_engagement(policy_name),
           }
           
           return metrics
   ```

5. **Reward Shaping for Long-Term Optimization:**
   ```python
   class LongTermRewardDesigner:
       """
       Design rewards that prevent short-term gaming while 
       encouraging long-term user value.
       """
       
       def compute_reward(self, user_id, item_id, interaction):
           immediate_reward = self.immediate_reward(interaction)
           
           # Long-term component (requires delayed feedback)
           long_term_reward = self.estimate_long_term_value(user_id, item_id)
           
           # Combine with discount factor
           gamma = 0.95  # Value future satisfaction at 95% of present
           total_reward = immediate_reward + gamma * long_term_reward
           
           return total_reward
       
       def estimate_long_term_value(self, user_id, item_id):
           """
           Proxy for long-term value when true outcome is delayed.
           Train a separate model that predicts:
           - Will user return tomorrow?
           - Will user's overall engagement increase?
           - Will user stay subscribed?
           """
           features = {
               'session_satisfaction_so_far': self.get_session_satisfaction(user_id),
               'content_quality_score': self.get_quality(item_id),
               'novelty_score': self.get_novelty(user_id, item_id),
               'user_growth_potential': self.get_growth_potential(user_id),
           }
           
           return self.ltv_model.predict(features)
       
       def anti_reward_hacking(self):
           """
           Common reward hacking patterns to prevent:
           1. Showing addictive but low-value content (maximize time, not value)
           2. Creating urgency/FOMO (engagement up, satisfaction down)
           3. Exploiting completionism (watch next, infinite scroll)
           4. Filter bubbles (safe content = high engagement, low growth)
           
           Countermeasures:
           - Include satisfaction surveys in reward
           - Include diversity in reward
           - Include retention (not just session engagement)
           - Penalize regret signals (quick back, report, mute)
           """
           pass
   ```
