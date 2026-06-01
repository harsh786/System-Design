# Graph Neural Networks

## Why Graphs?

Many real-world data has relational structure that tensors cannot naturally represent:

```
Social Networks:    Users (nodes) + Friendships (edges)
Molecules:          Atoms (nodes) + Bonds (edges)  
Knowledge Graphs:   Entities (nodes) + Relations (edges)
Code:               Functions (nodes) + Calls (edges)
Traffic:            Intersections (nodes) + Roads (edges)
Recommendations:    Users + Items (bipartite graph)
```

Graphs are the most general data structure — sequences and grids are special cases.

## Graph Fundamentals

```
Graph G = (V, E) where V = nodes, E = edges

Adjacency Matrix A ∈ {0,1}^(n×n):
  A[i,j] = 1 if edge (i,j) exists

Degree Matrix D:
  D[i,i] = Σⱼ A[i,j]  (number of neighbors)

Feature Matrix X ∈ ℝ^(n×d):
  Each node has a d-dimensional feature vector

Normalized Adjacency:
  Â = D^(-1/2) × A × D^(-1/2)  (symmetric normalization)
```

```
Example graph:
    1 --- 2
    |   / |
    |  /  |
    3 --- 4

A = [[0,1,1,0],    D = [[2,0,0,0],
     [1,0,1,1],         [0,3,0,0],
     [1,1,0,1],         [0,0,3,0],
     [0,1,1,0]]         [0,0,0,2]]
```

## Message Passing Framework

The unified view of most GNNs:

```
For each layer l:
  1. MESSAGE:    m_ij = MSG(h_i^l, h_j^l, e_ij)
  2. AGGREGATE:  M_i = AGG({m_ij : j ∈ N(i)})  
  3. UPDATE:     h_i^(l+1) = UPDATE(h_i^l, M_i)

┌──────────────────────────────────────────────┐
│  Node i collects messages from neighbors     │
│  Aggregates them (sum, mean, max, attention) │
│  Updates its own representation              │
│  After K layers: node "sees" K-hop neighborhood │
└──────────────────────────────────────────────┘

     h_j ──MSG──→ m_ij ─┐
     h_k ──MSG──→ m_ik ─┼─AGG─→ M_i ──UPDATE──→ h_i^(l+1)
     h_l ──MSG──→ m_il ─┘           ↑
                                    h_i^l
```

## Graph Convolutional Networks (GCN)

### Spectral Motivation

Graph convolution in spectral domain:
```
g_θ ⋆ x = U g_θ(Λ) U᙮ x

Where L = I - D^(-1/2)AD^(-1/2) = UΛU᙮ (graph Laplacian eigendecomposition)
```

### Kipf & Welling (2017) Simplification

```
H^(l+1) = σ(Ã H^l W^l)

Where:
  Ã = D̃^(-1/2) Ã D̃^(-1/2)   (normalized adjacency with self-loops)
  Ã = A + I                    (add self-loops)
  D̃[i,i] = Σⱼ Ã[i,j]
  W^l ∈ ℝ^(d_l × d_(l+1))    (learnable weight matrix)
  σ = activation (ReLU)

Per-node: h_i^(l+1) = σ(Σ_{j∈N(i)∪{i}} (1/√(d̃_i d̃_j)) × h_j^l × W^l)
```

### Simple GCN Implementation

```python
import torch
import torch.nn as nn
import torch.nn.functional as F

class GCNLayer(nn.Module):
    def __init__(self, in_features, out_features):
        super().__init__()
        self.W = nn.Linear(in_features, out_features, bias=False)
    
    def forward(self, X, A_hat):
        """
        X: Node features [n, in_features]
        A_hat: Normalized adjacency with self-loops [n, n]
        """
        return A_hat @ self.W(X)  # Aggregate then transform

class GCN(nn.Module):
    def __init__(self, n_features, n_hidden, n_classes):
        super().__init__()
        self.layer1 = GCNLayer(n_features, n_hidden)
        self.layer2 = GCNLayer(n_hidden, n_classes)
    
    def forward(self, X, A_hat):
        H = F.relu(self.layer1(X, A_hat))
        H = F.dropout(H, p=0.5, training=self.training)
        return self.layer2(H, A_hat)

# Preprocessing: compute normalized adjacency
def normalize_adjacency(A):
    A_tilde = A + torch.eye(A.size(0))  # Add self-loops
    D_tilde = A_tilde.sum(dim=1)
    D_inv_sqrt = torch.diag(D_tilde.pow(-0.5))
    return D_inv_sqrt @ A_tilde @ D_inv_sqrt

# Training for node classification
model = GCN(n_features=1433, n_hidden=64, n_classes=7)  # Cora dataset
optimizer = torch.optim.Adam(model.parameters(), lr=0.01, weight_decay=5e-4)

A_hat = normalize_adjacency(A)
for epoch in range(200):
    model.train()
    logits = model(X, A_hat)
    loss = F.cross_entropy(logits[train_mask], labels[train_mask])
    loss.backward()
    optimizer.step()
    optimizer.zero_grad()
```

## GraphSAGE (Sampling and Aggregating)

Key innovation: **inductive** learning via neighborhood sampling.

```
Algorithm:
  For each layer k = 1..K:
    For each node v:
      1. Sample fixed-size neighborhood: N_s(v) ⊂ N(v)
      2. Aggregate: h_N(v) = AGG_k({h_u^(k-1) : u ∈ N_s(v)})
      3. Concatenate: h_v^k = σ(W^k · CONCAT(h_v^(k-1), h_N(v)))
      4. Normalize: h_v^k = h_v^k / ||h_v^k||

Aggregators:
  - Mean: h_N = mean({h_u})
  - LSTM: h_N = LSTM(permuted {h_u})  
  - Pool: h_N = max(σ(W_pool h_u + b))
```

Advantage: Can generalize to unseen nodes (inductive).

## Graph Attention Networks (GAT)

Use **attention** to learn importance of each neighbor:

```
Attention coefficient:
  e_ij = LeakyReLU(a᙮ [W h_i || W h_j])
  
  α_ij = softmax_j(e_ij) = exp(e_ij) / Σ_{k∈N(i)} exp(e_ik)

Aggregation:
  h_i' = σ(Σ_{j∈N(i)} α_ij W h_j)

Multi-head attention (K heads):
  h_i' = ||_{k=1}^K σ(Σ_{j∈N(i)} α_ij^k W^k h_j)

┌─────────────────────────────────────┐
│ Unlike GCN: neighbors contribute    │
│ DIFFERENT amounts based on learned  │
│ attention weights, not just degree  │
└─────────────────────────────────────┘
```

## Graph Isomorphism Network (GIN)

Maximally powerful GNN (as powerful as WL test):

```
h_v^(k) = MLP^(k)((1 + ε^(k)) · h_v^(k-1) + Σ_{u∈N(v)} h_u^(k-1))

Key insight: SUM aggregation (not mean/max) is needed for 
maximum discriminative power.

Theorem: GIN is as powerful as the Weisfeiler-Leman graph 
isomorphism test (1-WL). No message-passing GNN can be MORE powerful.
```

## Tasks on Graphs

```
┌─────────────────────────────────────────────────────────────┐
│ Node Classification:                                         │
│   Input: Graph + some labeled nodes                          │
│   Output: Labels for all nodes                               │
│   Example: Classify papers by topic in citation network      │
│   Readout: Use node embedding directly → classifier          │
│                                                              │
│ Link Prediction:                                             │
│   Input: Graph with some edges missing                       │
│   Output: Probability of edge existence                      │
│   Example: Friend recommendation, knowledge graph completion │
│   Readout: score(u,v) = σ(h_u᙮ h_v) or MLP(h_u || h_v)    │
│                                                              │
│ Graph Classification:                                        │
│   Input: Multiple graphs, each with a label                  │
│   Output: Label per graph                                    │
│   Example: Molecule → toxic/non-toxic                        │
│   Readout: h_G = READOUT({h_v : v ∈ G})                    │
│            (sum, mean, or hierarchical pooling)               │
└─────────────────────────────────────────────────────────────┘
```

## Knowledge Graphs and Graph Embeddings

```
Knowledge Graph: (head, relation, tail) triples
  (Einstein, born_in, Germany)
  (Einstein, field, Physics)

Embedding methods — score function f(h, r, t):

TransE:  f = -||h + r - t||
  → relation as translation in embedding space
  
ComplEx: f = Re(⟨h, r, t̄⟩)
  → complex-valued embeddings, handles asymmetric relations

RotatE: f = -||h ∘ r - t||
  → relation as rotation, handles composition

DistMult: f = ⟨h, r, t⟩
  → simple but only symmetric relations
```

## Temporal Graphs

Graphs that change over time:

```
Approaches:
1. Discrete snapshots: G₁, G₂, ..., G_T → GNN + RNN/Transformer
2. Continuous time: events (u, v, t, type)
   - TGAT: temporal graph attention
   - TGN: temporal graph network with memory

Memory module: m_i(t) updated after each interaction
  m_i(t⁺) = MSG(m_i(t⁻), m_j(t⁻), Δt, edge_features)
```

## Scalability

Full-batch GCN requires entire adjacency matrix → doesn't scale.

```
Mini-batch approaches:
┌─────────────────────────────────────────────┐
│ 1. Neighbor Sampling (GraphSAGE)            │
│    Sample K neighbors per layer             │
│    Cost: O(K^L × batch_size)                │
│                                             │
│ 2. Cluster-GCN                              │
│    Partition graph into clusters             │
│    Train on subgraph per cluster            │
│                                             │
│ 3. GraphSAINT                               │
│    Sample subgraphs (node/edge/random walk) │
│    Correct bias with normalization          │
└─────────────────────────────────────────────┘
```

## Applications

### Drug Discovery
- Molecules as graphs → predict properties (toxicity, binding affinity)
- Generate novel molecules (graph VAE, graph diffusion)

### Fraud Detection
- Transaction graph: users + transactions
- Fraudsters form unusual subgraph patterns
- GNN detects based on local neighborhood structure

### Recommendation Systems
- User-item bipartite graph
- GNN learns embeddings capturing collaborative filtering
- PinSage (Pinterest): 3B nodes, 18B edges

## PyTorch Geometric Example

```python
import torch
from torch_geometric.nn import GCNConv, GATConv, global_mean_pool
from torch_geometric.datasets import Planetoid, TUDataset
from torch_geometric.loader import DataLoader

# Node classification on Cora
dataset = Planetoid(root='/tmp', name='Cora')
data = dataset[0]

class GATModel(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.conv1 = GATConv(dataset.num_features, 8, heads=8, dropout=0.6)
        self.conv2 = GATConv(8*8, dataset.num_classes, heads=1, dropout=0.6)
    
    def forward(self, data):
        x, edge_index = data.x, data.edge_index
        x = F.dropout(x, p=0.6, training=self.training)
        x = F.elu(self.conv1(x, edge_index))
        x = F.dropout(x, p=0.6, training=self.training)
        x = self.conv2(x, edge_index)
        return F.log_softmax(x, dim=1)

# Graph classification on MUTAG
dataset = TUDataset(root='/tmp', name='MUTAG')
loader = DataLoader(dataset, batch_size=32, shuffle=True)

class GraphClassifier(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.conv1 = GCNConv(dataset.num_features, 64)
        self.conv2 = GCNConv(64, 64)
        self.fc = torch.nn.Linear(64, dataset.num_classes)
    
    def forward(self, data):
        x, edge_index, batch = data.x, data.edge_index, data.batch
        x = F.relu(self.conv1(x, edge_index))
        x = F.relu(self.conv2(x, edge_index))
        x = global_mean_pool(x, batch)  # Graph-level readout
        return self.fc(x)
```

## Expressiveness Limitations

```
WL Test Hierarchy:
  1-WL ≡ Message Passing GNNs (GCN, GAT, GIN)
  Cannot distinguish: regular graphs, some non-isomorphic graphs

Solutions for more power:
  - Higher-order GNNs (k-WL): operate on k-tuples
  - Random features / positional encodings
  - Subgraph GNNs
  - Graph Transformers (attend to all nodes, not just neighbors)
```

## Interview Questions

1. Explain the message passing framework and how GCN fits into it.
2. What are the expressiveness limitations of standard GNNs?
3. How does GAT differ from GCN? When would you prefer one?
4. How would you scale a GNN to a graph with billions of edges?
5. Explain over-smoothing in deep GNNs and how to mitigate it.
6. How would you apply GNNs to fraud detection?
7. What is the relationship between GCN and spectral graph theory?

## Key Papers

- Kipf & Welling, "Semi-Supervised Classification with GCNs" (2017)
- Hamilton et al., "Inductive Representation Learning on Large Graphs" (GraphSAGE, 2017)
- Veličković et al., "Graph Attention Networks" (2018)
- Xu et al., "How Powerful are Graph Neural Networks?" (GIN, 2019)
- Ying et al., "Graph Convolutional Neural Networks for Web-Scale Recommender Systems" (PinSage, 2018)
- Gilmer et al., "Neural Message Passing for Quantum Chemistry" (2017)
