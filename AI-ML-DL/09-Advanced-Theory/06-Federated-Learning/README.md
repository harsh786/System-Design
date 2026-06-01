# Federated Learning

## Why Federated Learning?

```
Traditional ML:         Federated Learning:
  Data → Central Server    Data STAYS on device
  Train centrally          Model goes TO data
  Privacy risk             Privacy preserved
  
┌──────────────────────────────────────────────────────────┐
│ Motivations:                                              │
│ 1. Privacy: GDPR, HIPAA — data cannot leave device       │
│ 2. Communication: Data too large to transmit (edge/IoT)  │
│ 3. Data sovereignty: Cross-org collaboration without     │
│    sharing raw data                                       │
│ 4. Regulatory: Healthcare, finance data restrictions     │
└──────────────────────────────────────────────────────────┘
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Central Server                         │
│              (aggregates model updates)                   │
│                   ┌─────────┐                           │
│                   │ Global  │                            │
│                   │ Model   │                            │
│                   └────┬────┘                            │
│              ┌─────────┼─────────┐                      │
│              ↓         ↓         ↓                      │
│         ┌────────┐ ┌────────┐ ┌────────┐               │
│         │Client 1│ │Client 2│ │Client 3│               │
│         │Local   │ │Local   │ │Local   │               │
│         │Data    │ │Data    │ │Data    │               │
│         └────────┘ └────────┘ └────────┘               │
│                                                         │
│ Round:                                                   │
│  1. Server sends global model to selected clients        │
│  2. Clients train locally on private data               │
│  3. Clients send model UPDATES (not data) to server     │
│  4. Server aggregates updates → new global model        │
│  5. Repeat                                              │
└─────────────────────────────────────────────────────────┘
```

## Federated Averaging (FedAvg)

McMahan et al. (2017) — the foundational algorithm:

```
┌──────────────────────────────────────────────────────────────┐
│ Algorithm: FedAvg                                             │
│                                                              │
│ Server:                                                       │
│   Initialize global model w₀                                  │
│   for each round t = 1, 2, ..., T:                           │
│     Select subset S_t of K clients (fraction C)              │
│     Send w_t to all clients in S_t                           │
│     for each client k ∈ S_t (in parallel):                   │
│       w_k^(t+1) = ClientUpdate(k, w_t)                       │
│     Aggregate:                                               │
│       w_(t+1) = Σ_k (n_k/n) × w_k^(t+1)                   │
│                  ↑ weighted by local dataset size             │
│                                                              │
│ ClientUpdate(k, w):                                          │
│   B = split local data into batches                          │
│   for each local epoch e = 1, ..., E:                        │
│     for each batch b ∈ B:                                    │
│       w = w - η ∇L(w; b)                                    │
│   return w                                                    │
└──────────────────────────────────────────────────────────────┘

Hyperparameters:
  C = fraction of clients per round (e.g., 0.1)
  E = local epochs (more = less communication, but more drift)
  B = local batch size
  η = local learning rate
```

```python
import torch
import copy

class FedAvgServer:
    def __init__(self, global_model, client_datasets, rounds=100,
                 clients_per_round=10, local_epochs=5, lr=0.01):
        self.global_model = global_model
        self.client_datasets = client_datasets
        self.rounds = rounds
        self.clients_per_round = clients_per_round
        self.local_epochs = local_epochs
        self.lr = lr
    
    def train(self):
        for round_t in range(self.rounds):
            # Select clients
            selected = np.random.choice(
                len(self.client_datasets), self.clients_per_round, replace=False
            )
            
            # Local training
            client_weights = []
            client_sizes = []
            for k in selected:
                local_model = copy.deepcopy(self.global_model)
                local_model = self.client_update(local_model, self.client_datasets[k])
                client_weights.append(local_model.state_dict())
                client_sizes.append(len(self.client_datasets[k]))
            
            # Aggregate (weighted average)
            self.aggregate(client_weights, client_sizes)
    
    def client_update(self, model, dataset):
        optimizer = torch.optim.SGD(model.parameters(), lr=self.lr)
        loader = DataLoader(dataset, batch_size=32, shuffle=True)
        model.train()
        for _ in range(self.local_epochs):
            for x, y in loader:
                loss = F.cross_entropy(model(x), y)
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
        return model
    
    def aggregate(self, client_weights, client_sizes):
        total = sum(client_sizes)
        new_state = {}
        for key in client_weights[0]:
            new_state[key] = sum(
                w[key] * (n/total) for w, n in zip(client_weights, client_sizes)
            )
        self.global_model.load_state_dict(new_state)
```

## Communication Efficiency

Communication is the bottleneck (not compute):

```
Techniques:
┌────────────────────────────────────────────────────────┐
│ 1. Gradient Compression                                 │
│    - Top-K sparsification (send only largest gradients)│
│    - Quantization (FP32 → INT8 or 1-bit)              │
│    - Error feedback (accumulate unsent gradients)       │
│                                                        │
│ 2. Fewer Rounds                                        │
│    - More local epochs E (but causes client drift)     │
│    - Local SGD with periodic averaging                 │
│                                                        │
│ 3. Model Compression                                   │
│    - Send only delta: Δw = w_local - w_global          │
│    - Knowledge distillation to smaller model           │
│    - Federated distillation (share logits not weights) │
└────────────────────────────────────────────────────────┘
```

## Non-IID Data Challenges

The hardest problem in FL: clients have different data distributions.

```
Types of heterogeneity:
  - Label skew: Client A has mostly cats, Client B mostly dogs
  - Feature skew: Different camera angles/lighting per client
  - Quantity skew: Some clients have 10x more data
  - Temporal skew: Data arrives at different times

Impact: FedAvg diverges with high non-IID-ness!

Solutions:
  1. FedProx: Add proximal term ||w - w_global||² to local loss
     → prevents clients from drifting too far
  
  2. SCAFFOLD: Variance reduction via control variates
     → corrects for client drift directions
  
  3. Per-FedAvg: Personalized FL (MAML-inspired)
     → global model as initialization, personalize locally
  
  4. FedBN: Keep batch norm layers local
     → handles feature distribution shift

  5. Clustered FL: Group similar clients
     → separate models for different distributions
```

## Differential Privacy in Federated Learning

```
Even model updates can leak information!
  - Gradient inversion attacks can reconstruct training data
  - Membership inference: was this sample in training?

Differential Privacy (DP):
  A mechanism M is (ε, δ)-DP if for neighboring datasets D, D':
  P[M(D) ∈ S] ≤ e^ε × P[M(D') ∈ S] + δ

DP-FedAvg:
  1. Clip per-client update: Δw_k = Δw_k × min(1, C/||Δw_k||)
  2. Add noise: Δw_agg = (1/K)Σ_k Δw_k + N(0, σ²C²/K²)
  3. σ calibrated to achieve (ε, δ)-DP via moments accountant

Trade-off: stronger privacy (smaller ε) → more noise → worse model
```

## Secure Aggregation

```
Goal: Server learns ONLY the aggregate, not individual updates.

Protocol (simplified):
  1. Each client k generates random mask m_k
  2. Pairs of clients agree on shared masks (via Diffie-Hellman):
     Client i adds s_ij, Client j subtracts s_ij → cancels in sum!
  3. Server receives w_k + m_k from each client
  4. Masks cancel in aggregation: Σ(w_k + m_k) = Σw_k + 0

Handles dropouts via secret sharing (Shamir's threshold scheme)
```

## Split Learning

```
Alternative to FL: split model between client and server.

┌─────────┐       ┌─────────────────────┐
│ Client  │       │      Server          │
│ Layer 1 │──────→│ Layer 2, 3, ..., L   │
│ Layer 1 │←──────│ (gradients back)     │
└─────────┘       └─────────────────────┘
     ↑
  Raw data
  never leaves

Advantages:
  - Client needs minimal compute
  - Raw data never transmitted
  
Disadvantages:
  - Sequential (one client at a time)
  - Activations may leak info (smashed data attacks)
```

## Federated Fine-Tuning of LLMs

```
Challenge: LLMs are 7B-70B+ parameters — can't fit on device!

Approaches:
┌────────────────────────────────────────────────────────────┐
│ 1. Federated LoRA                                          │
│    - Each client fine-tunes only LoRA adapters (0.1% params)│
│    - Communicate tiny rank-r matrices                      │
│    - Server aggregates adapters, not full model            │
│                                                            │
│ 2. Federated Prompt Tuning                                 │
│    - Only tune soft prompt tokens                          │
│    - Even smaller communication (few hundred params)       │
│                                                            │
│ 3. Offsite Tuning                                          │
│    - Server sends compressed/distilled model to clients    │
│    - Clients tune the emulator                             │
│    - Server applies learned updates to full model          │
└────────────────────────────────────────────────────────────┘
```

## Applications

### Healthcare
- Hospitals collaborate on diagnosis models without sharing patient data
- NVIDIA FLARE: FL for medical imaging across institutions
- Example: Brain tumor segmentation across 71 sites (FeTS challenge)

### Mobile Keyboard (Google Gboard)
- Next-word prediction trained on user typing data
- Data never leaves phone
- FedAvg + DP + Secure Aggregation in production

### Finance
- Banks detect fraud collaboratively without sharing transactions
- Anti-money laundering across institutions
- Credit scoring without pooling credit data

## Challenges and Open Problems

```
1. Systems heterogeneity: Devices have different compute/bandwidth
2. Adversarial clients: Byzantine-robust aggregation needed
3. Model poisoning: Malicious client sends bad updates
4. Fairness: Model shouldn't be worse for minority data distributions
5. Catastrophic forgetting: Clients' data evolves over time
6. Incentive mechanisms: Why should clients participate?
7. Debugging: Can't inspect client data when model fails
```

## Interview Questions

1. Explain FedAvg and why more local epochs can hurt with non-IID data.
2. How does differential privacy protect against gradient inversion attacks?
3. Compare federated learning with split learning — trade-offs?
4. How would you handle a client with adversarial updates?
5. Design a federated learning system for a hospital consortium.
6. How would you federate fine-tuning of a 70B parameter LLM?
7. What are the communication bottlenecks and how do you address them?

## Key Papers

- McMahan et al., "Communication-Efficient Learning of Deep Networks (FedAvg)" (2017)
- Kairouz et al., "Advances and Open Problems in Federated Learning" (2021)
- Li et al., "Federated Optimization in Heterogeneous Networks (FedProx)" (2020)
- Bonawitz et al., "Towards Federated Learning at Scale (Google)" (2019)
- Abadi et al., "Deep Learning with Differential Privacy" (2016)
- Zhang et al., "Federated Learning with LoRA" (2023)
