# Recurrent Neural Networks (RNNs)

## 1. Why Sequences Need Special Architectures

Standard MLPs/CNNs assume fixed-size inputs with no temporal ordering. Sequences (text, audio, time series) have:
- **Variable length**
- **Temporal dependencies** (word meaning depends on context)
- **Parameter sharing** across time steps

## 2. Vanilla RNN Architecture

### Core Idea: Hidden State as Memory

```
      x₁        x₂        x₃        x₄
       ↓         ↓         ↓         ↓
h₀ → [RNN] → h₁[RNN] → h₂[RNN] → h₃[RNN] → h₄
       ↓         ↓         ↓         ↓
      y₁        y₂        y₃        y₄
```

### Equations

```
hₜ = tanh(Wₕₕ · hₜ₋₁ + Wₓₕ · xₜ + bₕ)    ← hidden state update
yₜ = Wₕᵧ · hₜ + bᵧ                          ← output
```

Parameters are SHARED across all time steps: Wₕₕ, Wₓₕ, Wₕᵧ, bₕ, bᵧ

### Unrolled Computation Graph

```
    x₁          x₂          x₃
     │           │           │
     ↓           ↓           ↓
  ┌──────┐   ┌──────┐   ┌──────┐
  │Wₓₕ·x│   │Wₓₕ·x│   │Wₓₕ·x│
  └──┬───┘   └──┬───┘   └──┬───┘
     │           │           │
h₀──→(+)──tanh──→(+)──tanh──→(+)──tanh──→ h₃
  ↗  │        ↗  │        ↗  │
Wₕₕ·h      Wₕₕ·h      Wₕₕ·h
     │           │           │
     ↓           ↓           ↓
  ┌──────┐   ┌──────┐   ┌──────┐
  │Wₕᵧ·h│   │Wₕᵧ·h│   │Wₕᵧ·h│
  └──┬───┘   └──┬───┘   └──┬───┘
     ↓           ↓           ↓
    y₁          y₂          y₃
```

### Implementation

```python
import torch
import torch.nn as nn

class VanillaRNN(nn.Module):
    def __init__(self, input_size, hidden_size, output_size):
        super().__init__()
        self.hidden_size = hidden_size
        self.W_xh = nn.Linear(input_size, hidden_size)
        self.W_hh = nn.Linear(hidden_size, hidden_size, bias=False)
        self.W_hy = nn.Linear(hidden_size, output_size)
    
    def forward(self, x, h=None):
        # x: [batch, seq_len, input_size]
        batch_size, seq_len, _ = x.shape
        if h is None:
            h = torch.zeros(batch_size, self.hidden_size, device=x.device)
        
        outputs = []
        for t in range(seq_len):
            h = torch.tanh(self.W_xh(x[:, t]) + self.W_hh(h))
            outputs.append(self.W_hy(h))
        
        return torch.stack(outputs, dim=1), h  # [batch, seq_len, output_size]
```

## 3. Backpropagation Through Time (BPTT)

### The Process

Unroll the RNN for T time steps, then backpropagate through the entire graph:

```
L = Σₜ Lₜ(yₜ, ŷₜ)

∂L/∂W = Σₜ ∂Lₜ/∂W

For ∂Lₜ/∂Wₕₕ:
∂Lₜ/∂Wₕₕ = Σₖ₌₁ᵗ (∂Lₜ/∂hₜ · ∂hₜ/∂hₖ · ∂hₖ/∂Wₕₕ)

where ∂hₜ/∂hₖ = Πᵢ₌ₖ₊₁ᵗ ∂hᵢ/∂hᵢ₋₁ = Πᵢ₌ₖ₊₁ᵗ Wₕₕᵀ · diag(1 - hᵢ²)
```

### The Vanishing Gradient Problem in RNNs

```
∂hₜ/∂hₖ = Πᵢ₌ₖ₊₁ᵗ Wₕₕᵀ · diag(tanh'(zᵢ))

Since |tanh'(z)| ≤ 1:
- If ||Wₕₕ|| < 1: gradient vanishes exponentially (can't learn long-range deps)
- If ||Wₕₕ|| > 1: gradient explodes

For sequence length T:
- Gradient scales as ~ ||Wₕₕ||^(T-k) for dependency from step k to T
- T=100: if ||Wₕₕ|| = 0.9, gradient is 0.9¹⁰⁰ ≈ 0.00003 (vanished!)
```

**Solution**: LSTM and GRU with gating mechanisms.

### Truncated BPTT

In practice, don't backprop through entire sequence. Truncate to last K steps:
```python
# Process sequence in chunks, detach hidden state
for chunk in chunks:
    h = h.detach()  # Stop gradient flow beyond this chunk
    output, h = rnn(chunk, h)
    loss.backward()
```

## 4. LSTM (Long Short-Term Memory) — Hochreiter & Schmidhuber, 1997

### Core Idea: Cell State + Gates

The cell state cₜ acts as a "conveyor belt" — information flows unchanged unless gates modify it.

### Gate-by-Gate Explanation

```
LSTM Cell:
                         ┌───────────────────────────────────────────┐
                         │            Cell State (cₜ)                 │
            cₜ₋₁ ──────→×────────────(+)────────────────────────→ cₜ │
                         ↑             ↑                             │
                      forget        input gate                       │
                       gate         × new info                       │
                         │             │                             │
                    ┌────┴────┐  ┌─────┴────┐                       │
                    │ σ(fₜ)   │  │σ(iₜ)×c̃ₜ │                       │
                    └────┬────┘  └────┬─────┘                       │
                         │            │           ┌─────────┐        │
                         └────────────┴───────────│ σ(oₜ)   │        │
                                                  └────┬────┘        │
                                                       │             │
    hₜ₋₁ ──┐                                         ×──tanh(cₜ)──→ hₜ
            │                                          ↑
    xₜ  ───┴──→ [Concatenate] ──→ [4 linear transforms]
```

### LSTM Equations

```
Forget Gate:   fₜ = σ(Wf · [hₜ₋₁, xₜ] + bf)      ← what to forget from cell
Input Gate:    iₜ = σ(Wi · [hₜ₋₁, xₜ] + bi)      ← what to write
Candidate:     c̃ₜ = tanh(Wc · [hₜ₋₁, xₜ] + bc)   ← new candidate values
Cell Update:   cₜ = fₜ ⊙ cₜ₋₁ + iₜ ⊙ c̃ₜ          ← update cell state
Output Gate:   oₜ = σ(Wo · [hₜ₋₁, xₜ] + bo)      ← what to output
Hidden State:  hₜ = oₜ ⊙ tanh(cₜ)                  ← filtered output
```

### Why LSTM Solves Vanishing Gradients

```
∂cₜ/∂cₜ₋₁ = fₜ    (forget gate value, typically close to 1)

Gradient through cell state:
∂cT/∂c₁ = Πₜ₌₂ᵀ fₜ ≈ 1 if forget gates stay open

Compare to vanilla RNN:
∂hT/∂h₁ = Πₜ Wₕₕ·diag(tanh') → vanishes/explodes
```

The additive cell update (cₜ = fₜ⊙cₜ₋₁ + iₜ⊙c̃ₜ) vs multiplicative (hₜ = Wₕₕ·hₜ₋₁) is key.

### Implementation

```python
class LSTMModel(nn.Module):
    def __init__(self, vocab_size, embed_dim, hidden_dim, num_layers, num_classes):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embed_dim)
        self.lstm = nn.LSTM(embed_dim, hidden_dim, num_layers,
                           batch_first=True, dropout=0.3, bidirectional=True)
        self.fc = nn.Linear(hidden_dim * 2, num_classes)  # *2 for bidirectional
    
    def forward(self, x):
        embeds = self.embedding(x)                    # [B, T, E]
        lstm_out, (h_n, c_n) = self.lstm(embeds)      # [B, T, 2H]
        # Use last hidden states from both directions
        hidden = torch.cat([h_n[-2], h_n[-1]], dim=1) # [B, 2H]
        return self.fc(hidden)                        # [B, C]
```

## 5. GRU (Gated Recurrent Unit) — Cho et al., 2014

Simplified LSTM: merges cell state and hidden state, uses 2 gates instead of 3.

### GRU Equations

```
Reset Gate:    rₜ = σ(Wr · [hₜ₋₁, xₜ] + br)      ← how much past to forget
Update Gate:   zₜ = σ(Wz · [hₜ₋₁, xₜ] + bz)      ← interpolation factor
Candidate:     h̃ₜ = tanh(W · [rₜ ⊙ hₜ₋₁, xₜ] + b)
Hidden State:  hₜ = (1 - zₜ) ⊙ hₜ₋₁ + zₜ ⊙ h̃ₜ   ← interpolate old and new
```

### GRU Gate Diagram

```
                    hₜ₋₁ ──────────────────────────────────────────→ ×(1-z) ──(+)──→ hₜ
                      │                                                         ↑
                      ├──→ [σ] ──→ zₜ (update gate)                        ×z
                      │              │                                       │
                      ├──→ [σ] ──→ rₜ (reset gate)                       h̃ₜ
                      │              │                                       ↑
                      │              ↓                                    [tanh]
                      └────→ (× rₜ) ────────────────────────────────────→ [W]
                                                                            ↑
    xₜ ────────────────────────────────────────────────────────────────────┘
```

### LSTM vs GRU

| Aspect | LSTM | GRU |
|--------|------|-----|
| Gates | 3 (forget, input, output) | 2 (reset, update) |
| States | h and c (separate cell) | h only |
| Parameters | More (4 weight matrices) | Fewer (3 weight matrices) |
| Performance | Slightly better on long seqs | Comparable, faster training |
| Use when | Long dependencies critical | Faster training needed |

## 6. Bidirectional RNNs

Process sequence in both directions — useful when full context is available (not for generation).

```
Forward:   h₁→  h₂→  h₃→  h₄→
            ↑    ↑    ↑    ↑
           x₁   x₂   x₃   x₄
            ↓    ↓    ↓    ↓
Backward: ←h₁  ←h₂  ←h₃  ←h₄

Output at each step: [h→ₜ ; ←hₜ]  (concatenation)
```

Use cases: NER, POS tagging, sentiment (full sentence available)
NOT for: language modeling, real-time speech (future not available)

## 7. Encoder-Decoder Architecture

### Sequence-to-Sequence (Seq2Seq)

```
Encoder:                              Decoder:
x₁ → x₂ → x₃ → <EOS>              <SOS> → y₁ → y₂ → y₃ → <EOS>
 ↓    ↓    ↓    ↓                    ↓     ↓    ↓    ↓    ↓
[E]→ [E]→ [E]→ [E]───context───→  [D]→  [D]→ [D]→ [D]→ [D]
                  ↓    vector        ↓     ↓    ↓    ↓
              h_final ─────────→ h₀_dec   y₁   y₂   y₃   <EOS>
```

**Problem**: Entire input sequence compressed into single fixed-size context vector (bottleneck!)

**Solution**: Attention mechanism.

## 8. Attention Mechanism (Bahdanau et al., 2014)

### Idea: Let decoder look at ALL encoder hidden states, not just the last one.

```
At each decoder step t:
1. Compute alignment scores: eₜᵢ = score(sₜ₋₁, hᵢ)   for all encoder states hᵢ
2. Normalize:               αₜᵢ = softmax(eₜ)
3. Context vector:          cₜ = Σᵢ αₜᵢ · hᵢ          (weighted sum)
4. Decode:                  sₜ = f(sₜ₋₁, yₜ₋₁, cₜ)
```

### Score Functions

| Type | Formula | Notes |
|------|---------|-------|
| Dot | sᵀh | Simple, requires same dim |
| General | sᵀWh | Learnable |
| Additive (Bahdanau) | vᵀtanh(W₁s + W₂h) | Most general |

### Attention Visualization

```
Decoder step t=2 ("chat"):
                    Encoder hidden states
                    h₁("le") h₂("chat") h₃("est") h₄("noir")
Attention weights:   0.05      0.85       0.05       0.05
                      ↓          ↓          ↓          ↓
                    × h₁      × h₂      × h₃      × h₄
                      └──────────┴──────────┴──────────┘
                                     ↓
                              context = Σ αᵢhᵢ ≈ h₂
                                     ↓
                              Decoder: "cat"
```

## 9. Sequence-to-Sequence Applications

### Machine Translation

```python
class Seq2Seq(nn.Module):
    def __init__(self, encoder, decoder, device):
        super().__init__()
        self.encoder = encoder
        self.decoder = decoder
        self.device = device
    
    def forward(self, src, trg, teacher_forcing_ratio=0.5):
        batch_size, trg_len = trg.shape[0], trg.shape[1]
        outputs = torch.zeros(batch_size, trg_len, self.decoder.output_dim).to(self.device)
        
        encoder_outputs, hidden = self.encoder(src)
        
        input = trg[:, 0]  # <SOS> token
        for t in range(1, trg_len):
            output, hidden, attention = self.decoder(input, hidden, encoder_outputs)
            outputs[:, t] = output
            # Teacher forcing: use ground truth or model prediction
            if random.random() < teacher_forcing_ratio:
                input = trg[:, t]
            else:
                input = output.argmax(dim=1)
        
        return outputs
```

### Teacher Forcing

- **During training**: Feed ground truth previous token (faster convergence)
- **During inference**: Feed model's own prediction (autoregressive)
- **Scheduled sampling**: Gradually reduce teacher forcing ratio during training

## 10. Applications

### NLP
- Machine translation (Seq2Seq + Attention → Transformers)
- Text generation (language models)
- Named Entity Recognition (BiLSTM + CRF)
- Sentiment analysis

### Time Series
```python
class TimeSeriesLSTM(nn.Module):
    def __init__(self, input_features, hidden_size, forecast_horizon):
        super().__init__()
        self.lstm = nn.LSTM(input_features, hidden_size, num_layers=2,
                           batch_first=True, dropout=0.2)
        self.fc = nn.Linear(hidden_size, forecast_horizon)
    
    def forward(self, x):
        # x: [batch, lookback_window, features]
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])  # Use last time step
```

### Speech Recognition
- Audio → Mel spectrogram → BiLSTM/Transformer → CTC loss → Text
- Now dominated by Transformers (Whisper, Wav2Vec2)

## Training Tips

1. **Gradient clipping** is essential for RNNs: `clip_grad_norm_(params, max_norm=5.0)`
2. **Pack padded sequences** for variable-length inputs in batches
3. **Sort by length** in batches for efficient packing
4. **Bidirectional** when full context available
5. **Stack multiple layers** (2-4 typical) for deeper representations
6. **Dropout between layers**, not within recurrence

```python
# Handling variable-length sequences
from torch.nn.utils.rnn import pack_padded_sequence, pad_packed_sequence

# Sort by length (descending)
lengths = [len(seq) for seq in sequences]
packed = pack_padded_sequence(padded_input, lengths, batch_first=True, enforce_sorted=False)
output, hidden = lstm(packed)
output, _ = pad_packed_sequence(output, batch_first=True)
```

## Production Considerations

1. **RNNs are sequential** → can't parallelize across time → slow training
2. **Transformers have replaced RNNs** for most NLP tasks (parallelizable, better long-range)
3. **RNNs still useful for**: streaming/online inference, low-latency requirements, edge devices
4. **State-space models** (Mamba, S4) are a modern alternative: RNN-like inference speed + Transformer-like training parallelism

## Interview Questions

1. **Why do vanilla RNNs struggle with long sequences?** Vanishing gradients—gradient through Wₕₕ raised to power T vanishes/explodes.

2. **How does the forget gate solve vanishing gradients?** Cell state gradient ∂cₜ/∂cₜ₋₁ = fₜ (close to 1) → gradient flows unimpeded through cell state.

3. **LSTM vs GRU—when to use which?** GRU: faster, fewer params, similar performance for most tasks. LSTM: slightly better for very long dependencies due to separate cell state.

4. **What's teacher forcing and its problem?** Using ground truth as input during training. Problem: "exposure bias"—at inference, model sees its own (potentially wrong) predictions.

5. **Why was attention such a breakthrough?** Eliminated the information bottleneck of compressing entire input into one vector. Decoder can selectively focus on relevant parts.

6. **Can RNNs be parallelized?** Not across time steps (sequential dependency). Can parallelize across batch dimension. This is why Transformers won.

7. **What's the difference between many-to-one, one-to-many, many-to-many?** Many-to-one: sentiment analysis. One-to-many: image captioning. Many-to-many: translation, tagging.

8. **How does bidirectional help?** Captures both past and future context. Example: "I went to the bank to deposit money" vs "...to fish"—"bank" meaning depends on future words.
