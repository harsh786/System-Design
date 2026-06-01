# Recommendation Systems at Scale

## Overview

Production recommendation systems are multi-stage pipelines that must balance relevance, diversity, freshness, and fairness while serving millions of users with sub-100ms latency. They are among the most impactful ML systems in industry.

---

## 1. Production RecSys Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│           PRODUCTION RECOMMENDATION PIPELINE                      │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  User Request                                                     │
│       │                                                           │
│       ▼                                                           │
│  ┌─────────────────────────────────────┐                         │
│  │  CANDIDATE GENERATION (Retrieval)    │  Millions → Thousands  │
│  │  • Two-Tower ANN search             │  Latency: 10-20ms      │
│  │  • Multiple retrieval sources        │                         │
│  │  • Collaborative filtering           │                         │
│  │  • Content-based                     │                         │
│  └──────────────────┬──────────────────┘                         │
│                     │ ~1000 candidates                            │
│                     ▼                                             │
│  ┌─────────────────────────────────────┐                         │
│  │  RANKING (Scoring)                   │  Thousands → Hundreds  │
│  │  • Deep model (Wide&Deep, DCN, etc.) │  Latency: 20-50ms     │
│  │  • Rich features (user+item+context) │                         │
│  │  • Multi-task (engagement+revenue)   │                         │
│  └──────────────────┬──────────────────┘                         │
│                     │ ~100 scored items                           │
│                     ▼                                             │
│  ┌─────────────────────────────────────┐                         │
│  │  RE-RANKING (Policy Layer)           │  Hundreds → Final list │
│  │  • Diversity injection (MMR, DPP)    │  Latency: 5-10ms      │
│  │  • Business rules (freshness, boost) │                         │
│  │  • Fairness constraints              │                         │
│  │  • Exploration/exploitation          │                         │
│  └──────────────────┬──────────────────┘                         │
│                     │                                             │
│                     ▼                                             │
│              Final Recommendations                                │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. Two-Tower Model Architecture

```python
class TwoTowerModel(nn.Module):
    """Two-tower (dual encoder) for candidate retrieval"""
    
    def __init__(self, user_feat_dim, item_feat_dim, embed_dim=128):
        super().__init__()
        
        # User tower
        self.user_tower = nn.Sequential(
            nn.Linear(user_feat_dim, 256),
            nn.ReLU(), nn.BatchNorm1d(256),
            nn.Linear(256, 256),
            nn.ReLU(), nn.BatchNorm1d(256),
            nn.Linear(256, embed_dim),
            nn.functional.normalize  # L2 normalize
        )
        
        # Item tower
        self.item_tower = nn.Sequential(
            nn.Linear(item_feat_dim, 256),
            nn.ReLU(), nn.BatchNorm1d(256),
            nn.Linear(256, 256),
            nn.ReLU(), nn.BatchNorm1d(256),
            nn.Linear(256, embed_dim),
            nn.functional.normalize
        )
    
    def forward(self, user_features, item_features):
        user_emb = self.user_tower(user_features)
        item_emb = self.item_tower(item_features)
        # Cosine similarity (since L2 normalized)
        return torch.sum(user_emb * item_emb, dim=-1)
    
    def get_user_embedding(self, user_features):
        """At serving time: compute user embedding → ANN lookup"""
        return self.user_tower(user_features)
    
    def get_item_embedding(self, item_features):
        """Offline: pre-compute all item embeddings → ANN index"""
        return self.item_tower(item_features)


class TwoTowerTraining:
    """Training with in-batch negatives"""
    
    def compute_loss(self, user_embs, item_embs, temperature=0.1):
        # Similarity matrix: [batch, batch]
        logits = torch.mm(user_embs, item_embs.T) / temperature
        # Positives are on the diagonal
        labels = torch.arange(len(user_embs), device=logits.device)
        loss = F.cross_entropy(logits, labels)
        return loss
```

### Serving with ANN (Approximate Nearest Neighbors)

- Pre-compute all item embeddings offline → build ANN index
- At request time: compute user embedding → ANN search → top-K candidates
- Libraries: FAISS, ScaNN, Milvus, Pinecone
- Typical: 100M+ items, <10ms retrieval

---

## 3. Collaborative Filtering at Scale

### ALS on Spark (Implicit Feedback)

```python
from pyspark.ml.recommendation import ALS

# Implicit ALS (confidence-weighted)
als = ALS(
    rank=128,              # Embedding dimension
    maxIter=15,
    regParam=0.01,
    implicitPrefs=True,    # Implicit feedback
    alpha=40,              # Confidence scaling
    userCol="user_id",
    itemCol="item_id",
    ratingCol="interaction_count"
)
model = als.fit(interactions_df)

# Generate top-K for all users
recommendations = model.recommendForAllUsers(100)
```

### Scaling Challenges

- Matrix factorization: billions of interactions
- Distributed training: parameter server or AllReduce
- Incremental updates: don't retrain from scratch daily
- Item popularity bias: popular items dominate

---

## 4. Deep Learning for RecSys

### Wide & Deep (Google, 2016)

```python
class WideAndDeep(nn.Module):
    """Wide (memorization) + Deep (generalization)"""
    
    def __init__(self, wide_dim, deep_features, embed_dims, hidden_dims):
        super().__init__()
        # Wide: linear model on cross-product features
        self.wide = nn.Linear(wide_dim, 1)
        
        # Deep: embeddings + MLP
        self.embeddings = nn.ModuleList([
            nn.Embedding(n, d) for n, d in embed_dims
        ])
        deep_input_dim = sum(d for _, d in embed_dims) + len(deep_features)
        self.deep = nn.Sequential(
            nn.Linear(deep_input_dim, hidden_dims[0]),
            nn.ReLU(), nn.Dropout(0.1),
            nn.Linear(hidden_dims[0], hidden_dims[1]),
            nn.ReLU(), nn.Dropout(0.1),
            nn.Linear(hidden_dims[1], 1)
        )
    
    def forward(self, wide_input, categorical_inputs, dense_inputs):
        # Wide component
        wide_out = self.wide(wide_input)
        
        # Deep component
        emb_out = [emb(cat) for emb, cat in zip(self.embeddings, categorical_inputs)]
        deep_input = torch.cat(emb_out + [dense_inputs], dim=-1)
        deep_out = self.deep(deep_input)
        
        return torch.sigmoid(wide_out + deep_out)
```

### DeepFM

- Replace Wide with FM (Factorization Machine) for automatic feature interactions
- No manual feature engineering for cross features

### DCN (Deep & Cross Network)

```python
class CrossNetwork(nn.Module):
    """Explicit feature crossing layers"""
    
    def __init__(self, input_dim, num_layers):
        super().__init__()
        self.layers = nn.ModuleList([
            nn.Linear(input_dim, input_dim) for _ in range(num_layers)
        ])
    
    def forward(self, x0):
        x = x0
        for layer in self.layers:
            # x_{l+1} = x0 * (W * x_l + b) + x_l
            x = x0 * layer(x) + x
        return x
```

### DLRM (Facebook/Meta)

- Bottom MLPs for dense features
- Embedding tables for sparse features (massive — TBs of parameters)
- Feature interaction via dot products
- Top MLP for final prediction
- Challenges: embedding table sharding across GPUs

---

## 5. Sequential/Session-Based Recommendation

```python
class SASRec(nn.Module):
    """Self-Attentive Sequential Recommendation"""
    
    def __init__(self, n_items, max_len=50, d_model=64, n_heads=2, n_layers=2):
        super().__init__()
        self.item_embedding = nn.Embedding(n_items + 1, d_model, padding_idx=0)
        self.position_embedding = nn.Embedding(max_len, d_model)
        
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=n_heads, dim_feedforward=d_model*4,
            dropout=0.2, batch_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, n_layers)
        self.output = nn.Linear(d_model, n_items)
    
    def forward(self, item_sequence):
        # item_sequence: [batch, seq_len] - user's interaction history
        seq_len = item_sequence.size(1)
        positions = torch.arange(seq_len, device=item_sequence.device)
        
        x = self.item_embedding(item_sequence) + self.position_embedding(positions)
        
        # Causal mask (can only attend to past items)
        mask = torch.triu(torch.ones(seq_len, seq_len), diagonal=1).bool()
        
        x = self.transformer(x, mask=mask)
        
        # Predict next item from last position
        logits = self.output(x[:, -1, :])
        return logits
```

### Other Sequential Models

- **GRU4Rec**: GRU on session sequences (fast, simple)
- **BERT4Rec**: Masked item prediction (bidirectional)
- **Transformers4Rec**: NVIDIA's production-ready framework

---

## 6. Multi-Objective Optimization

### Typical Objectives

| Objective | Metric | Business Goal |
|-----------|--------|---------------|
| Engagement | CTR, watch time | User retention |
| Revenue | RPM, conversion | Monetization |
| Diversity | ILS, coverage | User satisfaction |
| Freshness | Age of content | Content ecosystem |
| Fairness | Exposure parity | Creator ecosystem |

### Approaches

```python
class MultiObjectiveRanker:
    """Combine multiple objectives into final score"""
    
    def score(self, predictions, weights=None):
        """Scalarization approach"""
        if weights is None:
            weights = {'engagement': 0.5, 'revenue': 0.3, 'diversity': 0.2}
        
        final_score = sum(w * predictions[obj] for obj, w in weights.items())
        return final_score
    
    def pareto_optimal(self, candidates, objectives):
        """Find Pareto-optimal set"""
        pareto_front = []
        for c in candidates:
            dominated = False
            for other in candidates:
                if all(other[obj] >= c[obj] for obj in objectives) and \
                   any(other[obj] > c[obj] for obj in objectives):
                    dominated = True
                    break
            if not dominated:
                pareto_front.append(c)
        return pareto_front
```

### Multi-Task Learning

- Shared bottom layers + task-specific towers
- MMoE (Multi-gate Mixture of Experts)
- PLE (Progressive Layered Extraction)
- Gradient balancing (PCGrad, GradNorm)

---

## 7. Cold Start Strategies

| Strategy | New Users | New Items |
|----------|-----------|-----------|
| Content-based | Use demographics, stated preferences | Use item metadata |
| Popularity | Recommend popular items | Boost new items |
| Bandits (ε-greedy, UCB, Thompson) | Explore systematically | Explore new items |
| Meta-learning | Few-shot from similar users | Transfer from similar items |
| Onboarding | Explicit preference elicitation | Creator-provided signals |

---

## 8. Real-Time Personalization

### Feature Freshness

```
┌──────────────────────────────────────────────┐
│         FEATURE FRESHNESS TIERS              │
├──────────────────────────────────────────────┤
│                                               │
│  Real-time (< 1 sec):                        │
│  • Last action in session                    │
│  • Current context (time, device, location)  │
│                                               │
│  Near-real-time (minutes):                   │
│  • Streaming aggregates (clicks last hour)   │
│  • Trending items                            │
│                                               │
│  Batch (hours/daily):                        │
│  • User embeddings                           │
│  • Item popularity scores                    │
│  • Collaborative filtering signals           │
│                                               │
│  Static:                                     │
│  • User demographics                         │
│  • Item metadata                             │
│                                               │
└──────────────────────────────────────────────┘
```

### Online Feature Store Architecture

- **Feast / Tecton / Redis**: Low-latency feature serving
- Streaming pipelines (Kafka + Flink) for real-time features
- Point-in-time correctness for training (avoid leakage)

---

## 9. Evaluation

### Offline Metrics

| Metric | Formula | Use Case |
|--------|---------|----------|
| NDCG@K | Normalized Discounted Cumulative Gain | Ranked list quality |
| Hit Rate@K | % users with ≥1 relevant item in top-K | Recall-oriented |
| MRR | Mean Reciprocal Rank | First relevant position |
| MAP@K | Mean Average Precision | Overall precision |
| Coverage | % items ever recommended | Diversity |
| ILS | Intra-List Similarity | Within-list diversity |

### Online Evaluation

- **A/B Testing**: Gold standard but slow (weeks for significance)
- **Interleaving**: Mix recommendations from A and B, observe preference
- **Bandits**: Continuous optimization without fixed experiments
- **Long-term metrics**: Retention, LTV (hard to attribute)

### Offline-Online Correlation

- Many offline improvements don't translate online
- Optimize for metrics that correlate with business KPIs
- Use replay methods for counterfactual evaluation

---

## 10. Diversity & Serendipity

```python
class DiversityReranker:
    """MMR-based diversity re-ranking"""
    
    def mmr_rerank(self, candidates, scores, embeddings, lambda_param=0.5, k=20):
        """Maximal Marginal Relevance"""
        selected = []
        remaining = list(range(len(candidates)))
        
        for _ in range(k):
            best_score = -float('inf')
            best_idx = -1
            
            for idx in remaining:
                relevance = scores[idx]
                
                # Max similarity to already selected items
                if selected:
                    sim_to_selected = max(
                        cosine_similarity(embeddings[idx], embeddings[s])
                        for s in selected
                    )
                else:
                    sim_to_selected = 0
                
                # MMR score: balance relevance vs diversity
                mmr = lambda_param * relevance - (1 - lambda_param) * sim_to_selected
                
                if mmr > best_score:
                    best_score = mmr
                    best_idx = idx
            
            selected.append(best_idx)
            remaining.remove(best_idx)
        
        return selected
```

---

## 11. Case Studies

### Netflix

- **Architecture**: Candidate generation (multiple sources) → Ranking → Row selection
- **Key innovations**: Contextual bandits for artwork personalization, session-based models
- **Scale**: 200M+ subscribers, 15K+ titles

### YouTube

- **Architecture**: Two-stage (deep candidate generation + deep ranking)
- **Key innovations**: Watch time prediction, multi-task (engagement + satisfaction)
- **Challenge**: Billions of videos, real-time user state

### Spotify

- **Architecture**: Hybrid (collaborative + content + audio features)
- **Key innovations**: Audio embeddings from raw audio, Discover Weekly (explore/exploit)
- **Challenge**: Cold start for new songs/podcasts

### Amazon

- **Architecture**: Item-to-item CF + personalized ranking
- **Key innovations**: "Customers who bought X also bought Y", session-aware
- **Challenge**: Massive catalog diversity, purchase intent prediction

---

## 12. Feature Engineering for RecSys

```python
class RecSysFeatures:
    """Common feature categories for recommendation"""
    
    def user_features(self, user_id):
        return {
            # Static
            'age_bucket': ..., 'country': ..., 'tenure_days': ...,
            # Behavioral (from feature store)
            'items_consumed_7d': ...,
            'avg_session_length': ...,
            'preferred_categories': ...,  # Top-5 category distribution
            'activity_hour_distribution': ...,
            # Embedding
            'user_embedding_128d': ...,  # From collaborative filtering
        }
    
    def item_features(self, item_id):
        return {
            # Metadata
            'category': ..., 'tags': ..., 'creator_id': ...,
            'age_days': ..., 'language': ...,
            # Popularity
            'impressions_7d': ..., 'ctr_7d': ...,
            'engagement_rate': ...,
            # Content
            'title_embedding': ..., 'content_embedding': ...,
            # Item embedding
            'item_embedding_128d': ...,
        }
    
    def context_features(self, request):
        return {
            'hour_of_day': ..., 'day_of_week': ...,
            'device_type': ..., 'platform': ...,
            'session_depth': ...,  # How many items already consumed
        }
    
    def cross_features(self, user_id, item_id):
        return {
            'user_item_category_affinity': ...,
            'user_creator_interaction_count': ...,
            'time_since_last_similar_item': ...,
        }
```

---

## Netflix-Scale System Design

```
┌────────────────────────────────────────────────────────────────┐
│              NETFLIX-SCALE RECOMMENDATION SYSTEM                 │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐                                              │
│  │  User Request │                                             │
│  └──────┬───────┘                                              │
│         │                                                       │
│         ▼                                                       │
│  ┌─────────────────────────────────────────────────┐           │
│  │ RETRIEVAL (Multiple Sources, in parallel)        │           │
│  │ ┌──────────┐ ┌──────────┐ ┌──────────┐         │           │
│  │ │Two-Tower │ │Trending  │ │Because   │ ...     │           │
│  │ │(personal)│ │(popular) │ │You Watch │         │           │
│  │ └──────────┘ └──────────┘ └──────────┘         │           │
│  └──────────────────────┬──────────────────────────┘           │
│                         │ ~2000 candidates                     │
│                         ▼                                       │
│  ┌─────────────────────────────────────────────────┐           │
│  │ FEATURE STORE (Redis + online computation)       │           │
│  │ User features + Item features + Context          │           │
│  └──────────────────────┬──────────────────────────┘           │
│                         │                                       │
│                         ▼                                       │
│  ┌─────────────────────────────────────────────────┐           │
│  │ RANKING MODEL (Multi-task deep model)            │           │
│  │ Predicts: P(click), P(watch>50%), P(finish),     │           │
│  │           P(add_to_list), E[watch_time]          │           │
│  └──────────────────────┬──────────────────────────┘           │
│                         │                                       │
│                         ▼                                       │
│  ┌─────────────────────────────────────────────────┐           │
│  │ RE-RANKING + PAGE COMPOSITION                    │           │
│  │ • Row generation (genre, "because you watched") │           │
│  │ • Diversity across rows                          │           │
│  │ • Artwork personalization (contextual bandit)    │           │
│  │ • Position bias correction                       │           │
│  └──────────────────────┬──────────────────────────┘           │
│                         │                                       │
│                         ▼                                       │
│  ┌─────────────────────────────────────────────────┐           │
│  │ RESPONSE (Personalized page with rows)           │           │
│  └─────────────────────────────────────────────────┘           │
│                                                                 │
│  OFFLINE PIPELINE:                                              │
│  ┌──────────┐ ┌──────────────┐ ┌──────────────────┐           │
│  │Event Log │→│ Training Data │→│ Model Training   │           │
│  │(Kafka)   │ │ (Spark)      │ │ (GPU cluster)    │           │
│  └──────────┘ └──────────────┘ └──────────────────┘           │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

---

## Production Considerations

- **Latency**: Total <100ms (P99), retrieval <20ms, ranking <50ms
- **Throughput**: 100K-1M+ QPS for major platforms
- **Feature freshness**: Balance freshness vs compute cost
- **Model updates**: Daily/hourly retraining, online learning for freshness
- **Position bias**: Correct for item position in training data
- **Feedback loops**: Popular gets more popular (use exploration)
- **Logging**: Log everything for offline evaluation and debugging

---

## Interview Questions

1. **Design a recommendation system for a new video streaming platform with 10M users and 100K videos. Walk through the full architecture.**
2. **How would you handle the cold-start problem for a new user who just signed up?**
3. **Explain the two-tower model. Why is it used for retrieval but not ranking?**
4. **How would you add diversity to recommendations without significantly hurting relevance?**
5. **Your offline NDCG improved by 5% but A/B test shows no engagement lift. Why? What would you investigate?**
6. **Design a feature store for real-time recommendation. What are the freshness tiers?**
7. **How do you handle position bias in training a ranking model?**
8. **Compare Wide&Deep, DCN, and DLRM. When would you choose each?**
9. **How would you balance engagement optimization vs user well-being (e.g., reducing addictive patterns)?**
10. **Design a multi-objective ranking system that balances CTR, watch time, and content diversity.**

---

## Key Papers

1. **"Deep Neural Networks for YouTube Recommendations"** - Covington et al. (2016)
2. **"Wide & Deep Learning"** - Cheng et al. (2016)
3. **"Deep & Cross Network"** - Wang et al. (2017, 2021 v2)
4. **"DLRM"** - Naumov et al. (2019)
5. **"SASRec"** - Kang & McAuley (2018)
6. **"Sampling-Bias-Corrected Neural Modeling"** - Yi et al. (2019) - Two-tower training
7. **"MMoE"** - Ma et al. (2018) - Multi-task for RecSys
8. **"Contextual Bandits for Recommendations"** - Li et al. (2010) - LinUCB
9. **"BERT4Rec"** - Sun et al. (2019)
10. **"On the Factory Floor: ML at Netflix"** - Blog series

---

## Common Pitfalls

| Pitfall | Consequence | Mitigation |
|---------|-------------|------------|
| Training on biased data | Popularity reinforcement | IPS weighting, exploration |
| Position bias in training | Model learns position, not relevance | Position feature, unbiased learning |
| Ignoring negative feedback | Recommend things users actively dislike | Model dislikes explicitly |
| Offline metric obsession | No online improvement | Focus on metrics that correlate with business |
| Feature leakage | Artificially high offline metrics | Strict temporal splits |
| Serving/training skew | Silent model degradation | Feature store consistency, monitoring |
| Over-personalization | Filter bubbles, user fatigue | Diversity injection, exploration |
