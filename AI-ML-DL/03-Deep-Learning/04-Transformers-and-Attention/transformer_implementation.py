"""
Complete Transformer Encoder Implementation from Scratch (NumPy only)
=====================================================================

This file implements every component of a Transformer encoder using only NumPy.
It is designed to be educational — every function includes detailed comments
explaining the mathematical intuition and implementation choices.

Author: Learning reference for Staff Architect level understanding
"""

import numpy as np

# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================


def softmax(x, axis=-1):
    """
    Numerically stable softmax.
    
    Why subtract max? Without it, exp(large_number) overflows to inf.
    Subtracting max doesn't change the result because:
        softmax(x - c) = exp(x - c) / Σexp(x - c) 
                       = exp(x)·exp(-c) / Σ(exp(x)·exp(-c))
                       = exp(x) / Σexp(x)  = softmax(x)
    """
    # Subtract max for numerical stability (prevents overflow in exp)
    x_shifted = x - np.max(x, axis=axis, keepdims=True)
    exp_x = np.exp(x_shifted)
    return exp_x / np.sum(exp_x, axis=axis, keepdims=True)


def gelu(x):
    """
    Gaussian Error Linear Unit — the activation function used in modern transformers.
    
    GELU(x) = x · Φ(x), where Φ is the cumulative distribution function of N(0,1).
    
    Unlike ReLU which hard-zeros negative values, GELU smoothly gates them.
    This helps because small negative activations can still contribute meaningful signal.
    
    Approximation: 0.5 * x * (1 + tanh(sqrt(2/π) * (x + 0.044715 * x³)))
    """
    return 0.5 * x * (1.0 + np.tanh(np.sqrt(2.0 / np.pi) * (x + 0.044715 * x**3)))


# ==============================================================================
# LAYER NORMALIZATION
# ==============================================================================


class LayerNorm:
    """
    Layer Normalization: normalizes across the feature dimension (last axis).
    
    Why LayerNorm instead of BatchNorm in Transformers?
    - BatchNorm normalizes across the batch dimension — problematic for variable-length
      sequences and doesn't work well with small batches during inference.
    - LayerNorm normalizes each sample independently across features, making it
      batch-size agnostic and stable for sequence models.
    
    Formula: y = (x - μ) / √(σ² + ε) * γ + β
    where μ, σ² are computed over the last dimension (d_model).
    γ (scale) and β (shift) are learnable parameters.
    """

    def __init__(self, d_model, eps=1e-6):
        self.eps = eps
        self.gamma = np.ones(d_model)   # Learnable scale, initialized to 1
        self.beta = np.zeros(d_model)   # Learnable shift, initialized to 0

    def forward(self, x):
        """
        x shape: (..., d_model) — normalize over last dimension
        
        The mean and variance are computed per-token (each position independently).
        This ensures each token's representation has zero mean and unit variance
        before being scaled/shifted by γ and β.
        """
        mean = np.mean(x, axis=-1, keepdims=True)
        var = np.var(x, axis=-1, keepdims=True)
        x_norm = (x - mean) / np.sqrt(var + self.eps)
        return self.gamma * x_norm + self.beta


# ==============================================================================
# POSITIONAL ENCODING
# ==============================================================================


class PositionalEncoding:
    """
    Sinusoidal Positional Encoding from "Attention Is All You Need".
    
    Why do we need this? Self-attention is permutation-equivariant — it treats
    "The cat sat on the mat" and "mat the on sat cat The" identically without
    position information. We must explicitly inject position awareness.
    
    Formula:
        PE(pos, 2i)   = sin(pos / 10000^(2i/d_model))
        PE(pos, 2i+1) = cos(pos / 10000^(2i/d_model))
    
    Why sinusoidal?
    1. Bounded: values always in [-1, 1], won't dominate token embeddings
    2. Unique: each position gets a distinct encoding
    3. Relative positions: PE(pos+k) is a linear function of PE(pos),
       allowing the model to learn relative offsets
    4. Generalizes: works for sequences longer than seen during training
    
    The different frequencies (controlled by i) create a "binary encoding" effect:
    - Low dimensions oscillate quickly (like least-significant bits)
    - High dimensions oscillate slowly (like most-significant bits)
    """

    def __init__(self, d_model, max_len=5000):
        self.d_model = d_model
        # Create position encoding matrix [max_len, d_model]
        pe = np.zeros((max_len, d_model))

        # Position indices: [0, 1, 2, ..., max_len-1]
        position = np.arange(max_len)[:, np.newaxis]  # Shape: [max_len, 1]

        # Division term: 10000^(2i/d_model) computed in log space for stability
        # log(10000^(2i/d)) = 2i/d * log(10000)
        div_term = np.exp(
            np.arange(0, d_model, 2) * -(np.log(10000.0) / d_model)
        )  # Shape: [d_model/2]

        # Apply sin to even indices, cos to odd indices
        pe[:, 0::2] = np.sin(position * div_term)  # Even dimensions
        pe[:, 1::2] = np.cos(position * div_term)  # Odd dimensions

        self.pe = pe  # Shape: [max_len, d_model]

    def forward(self, seq_len):
        """Return positional encoding for the given sequence length."""
        return self.pe[:seq_len, :]


# ==============================================================================
# SCALED DOT-PRODUCT ATTENTION
# ==============================================================================


def scaled_dot_product_attention(Q, K, V, mask=None):
    """
    Core attention mechanism: the heart of the Transformer.
    
    Shapes:
        Q: (..., seq_len_q, d_k)   — Queries: "what am I looking for?"
        K: (..., seq_len_k, d_k)   — Keys: "what do I contain?"
        V: (..., seq_len_k, d_v)   — Values: "what information do I provide?"
        mask: (..., seq_len_q, seq_len_k) — optional mask (0 = attend, -inf = block)
    
    Returns:
        output: (..., seq_len_q, d_v) — attention-weighted combination of values
        attention_weights: (..., seq_len_q, seq_len_k) — the attention pattern
    
    The algorithm:
    1. Compute similarity: QKᵀ gives an [n×n] matrix of how much each query
       matches each key. High dot product = high similarity.
    2. Scale by √d_k: Without this, dot products grow proportionally to d_k
       (if q,k entries are ~N(0,1), then q·k ~ N(0, d_k)). Large values push
       softmax into saturation where gradients vanish.
    3. Mask (optional): Set certain positions to -∞ so softmax gives them 0 weight.
       Used for: causal masking (decoder), padding masking.
    4. Softmax: Convert scores to a probability distribution (rows sum to 1).
    5. Multiply by V: Each output is a weighted sum of value vectors.
    """
    d_k = Q.shape[-1]

    # Step 1 & 2: Compute scaled attention scores
    # Q @ Kᵀ: [seq_q, d_k] × [d_k, seq_k] → [seq_q, seq_k]
    scores = np.matmul(Q, K.swapaxes(-2, -1)) / np.sqrt(d_k)

    # Step 3: Apply mask (if provided)
    if mask is not None:
        # Where mask is 0, replace with -inf (will become 0 after softmax)
        scores = np.where(mask == 0, -1e9, scores)

    # Step 4: Softmax over keys dimension (last axis)
    attention_weights = softmax(scores, axis=-1)

    # Step 5: Weighted sum of values
    output = np.matmul(attention_weights, V)

    return output, attention_weights


# ==============================================================================
# MULTI-HEAD ATTENTION
# ==============================================================================


class MultiHeadAttention:
    """
    Multi-Head Attention: run h parallel attention operations, then combine.
    
    Why multiple heads?
    A single attention head projects Q, K, V into one subspace. It can only
    capture ONE type of relationship per layer. Multiple heads allow the model
    to simultaneously attend to information from different representation subspaces:
    - Head 1 might learn syntactic relationships (subject-verb agreement)
    - Head 2 might learn positional proximity
    - Head 3 might learn coreference (pronoun → noun)
    
    The concatenated outputs are projected through W_O to mix information
    across heads — this is crucial for heads to "communicate" their findings.
    
    Dimensions:
        d_model = h × d_k (typically d_k = d_model / h)
        
    Cost: Same as single-head attention with full d_model dimension, because
    we split d_model across h heads rather than using h full-size heads.
    """

    def __init__(self, d_model, n_heads):
        assert d_model % n_heads == 0, "d_model must be divisible by n_heads"

        self.d_model = d_model
        self.n_heads = n_heads
        self.d_k = d_model // n_heads  # Dimension per head

        # Projection matrices (in practice these are nn.Linear layers)
        # Xavier/Glorot initialization: variance = 2/(fan_in + fan_out)
        scale = np.sqrt(2.0 / (d_model + d_model))
        self.W_q = np.random.randn(d_model, d_model) * scale
        self.W_k = np.random.randn(d_model, d_model) * scale
        self.W_v = np.random.randn(d_model, d_model) * scale
        self.W_o = np.random.randn(d_model, d_model) * scale

    def split_heads(self, x):
        """
        Reshape [batch, seq_len, d_model] → [batch, n_heads, seq_len, d_k]
        
        This is the key insight: we don't use separate weight matrices per head.
        Instead, we use ONE large projection (d_model → d_model) and then
        RESHAPE to split the last dimension into (n_heads, d_k).
        This is mathematically equivalent but computationally more efficient.
        """
        batch_size, seq_len, _ = x.shape
        x = x.reshape(batch_size, seq_len, self.n_heads, self.d_k)
        return x.transpose(0, 2, 1, 3)  # [batch, heads, seq, d_k]

    def combine_heads(self, x):
        """
        Reverse of split_heads: [batch, n_heads, seq_len, d_k] → [batch, seq_len, d_model]
        """
        batch_size, _, seq_len, _ = x.shape
        x = x.transpose(0, 2, 1, 3)  # [batch, seq, heads, d_k]
        return x.reshape(batch_size, seq_len, self.d_model)

    def forward(self, query, key, value, mask=None):
        """
        Full multi-head attention forward pass.
        
        For self-attention: query = key = value = x
        For cross-attention: query = decoder state, key = value = encoder output
        """
        # Project inputs through learned linear transformations
        Q = np.matmul(query, self.W_q)  # [batch, seq, d_model]
        K = np.matmul(key, self.W_k)
        V = np.matmul(value, self.W_v)

        # Split into multiple heads
        Q = self.split_heads(Q)  # [batch, heads, seq, d_k]
        K = self.split_heads(K)
        V = self.split_heads(V)

        # Apply scaled dot-product attention (independently per head)
        attn_output, attn_weights = scaled_dot_product_attention(Q, K, V, mask)

        # Concatenate heads and project
        concat = self.combine_heads(attn_output)  # [batch, seq, d_model]
        output = np.matmul(concat, self.W_o)      # Final linear projection

        return output, attn_weights


# ==============================================================================
# FEED-FORWARD NETWORK
# ==============================================================================


class FeedForward:
    """
    Position-wise Feed-Forward Network.
    
    Applied independently to each position (token). This is where the model
    does its "thinking" — attention gathers information, FFN processes it.
    
    Architecture: Linear(d_model → d_ff) → GELU → Linear(d_ff → d_model)
    
    Typically d_ff = 4 * d_model (expansion factor of 4).
    
    Why expand then contract?
    The expansion to a higher dimension allows the network to represent more
    complex functions. It's like the hidden layer of a small MLP applied
    independently at each position. The contraction brings it back to d_model
    so it can interface with attention layers.
    
    Recent insight (SwiGLU in LLaMA): Using gated activations like
    SwiGLU(x) = Swish(xW₁) ⊙ (xW₃) instead of GELU improves performance.
    """

    def __init__(self, d_model, d_ff):
        scale1 = np.sqrt(2.0 / (d_model + d_ff))
        scale2 = np.sqrt(2.0 / (d_ff + d_model))
        self.W1 = np.random.randn(d_model, d_ff) * scale1
        self.b1 = np.zeros(d_ff)
        self.W2 = np.random.randn(d_ff, d_model) * scale2
        self.b2 = np.zeros(d_model)

    def forward(self, x):
        """
        x: [batch, seq_len, d_model] → [batch, seq_len, d_model]
        
        Note: "position-wise" means the same weights are shared across all
        positions but applied independently. It's like a 1×1 convolution.
        """
        hidden = gelu(np.matmul(x, self.W1) + self.b1)  # [batch, seq, d_ff]
        output = np.matmul(hidden, self.W2) + self.b2    # [batch, seq, d_model]
        return output


# ==============================================================================
# TRANSFORMER ENCODER BLOCK
# ==============================================================================


class TransformerEncoderBlock:
    """
    One block of the Transformer encoder.
    
    Architecture (Pre-Norm variant, used in modern transformers like GPT-2+):
        x → LayerNorm → Multi-Head Attention → + (residual) →
          → LayerNorm → Feed-Forward → + (residual) → output
    
    Why Pre-Norm instead of Post-Norm (original paper)?
    - Pre-Norm: gradients flow more easily through residual connections
      because they bypass the normalization. Training is more stable,
      especially for deep networks (>12 layers).
    - Post-Norm: can achieve slightly better performance but requires
      careful learning rate warmup and is less stable.
    
    Residual connections are critical:
    - They allow gradients to flow directly through the network
    - They let each layer learn a DELTA (refinement) rather than a
      complete transformation — much easier to optimize
    - Without them, deep transformers cannot train at all
    """

    def __init__(self, d_model, n_heads, d_ff):
        self.attention = MultiHeadAttention(d_model, n_heads)
        self.feed_forward = FeedForward(d_model, d_ff)
        self.norm1 = LayerNorm(d_model)
        self.norm2 = LayerNorm(d_model)

    def forward(self, x, mask=None):
        """
        x: [batch, seq_len, d_model]
        Returns: [batch, seq_len, d_model]
        """
        # Sub-layer 1: Multi-head self-attention with residual connection
        normed = self.norm1.forward(x)
        attn_out, _ = self.attention.forward(normed, normed, normed, mask)
        x = x + attn_out  # Residual connection

        # Sub-layer 2: Feed-forward with residual connection
        normed = self.norm2.forward(x)
        ff_out = self.feed_forward.forward(normed)
        x = x + ff_out  # Residual connection

        return x


# ==============================================================================
# FULL TRANSFORMER ENCODER
# ==============================================================================


class TransformerEncoder:
    """
    Complete Transformer Encoder: stack of N identical encoder blocks.
    
    The full pipeline:
    1. Token embedding: map token IDs to dense vectors
    2. Positional encoding: add position information
    3. N × Encoder blocks: iteratively refine representations
    4. Final layer norm: stabilize output
    
    Each successive layer builds more abstract representations:
    - Early layers: local syntax, morphology
    - Middle layers: phrase-level semantics, basic relationships
    - Late layers: long-range dependencies, task-relevant features
    """

    def __init__(self, vocab_size, d_model, n_heads, d_ff, n_layers, max_seq_len):
        self.d_model = d_model

        # Token embedding: maps integer token IDs to d_model vectors
        self.token_embedding = np.random.randn(vocab_size, d_model) * 0.02

        # Positional encoding
        self.pos_encoding = PositionalEncoding(d_model, max_seq_len)

        # Stack of encoder blocks
        self.layers = [
            TransformerEncoderBlock(d_model, n_heads, d_ff)
            for _ in range(n_layers)
        ]

        # Final layer norm
        self.final_norm = LayerNorm(d_model)

    def forward(self, token_ids):
        """
        token_ids: [batch, seq_len] — integer token indices
        Returns: [batch, seq_len, d_model] — contextualized representations
        """
        batch_size, seq_len = token_ids.shape

        # Step 1: Token embedding lookup
        # Scale by √d_model to balance magnitude with positional encoding
        # (positional encoding has values in [-1, 1], embeddings need similar scale)
        x = self.token_embedding[token_ids] * np.sqrt(self.d_model)

        # Step 2: Add positional encoding
        x = x + self.pos_encoding.forward(seq_len)

        # Step 3: Pass through encoder blocks
        for layer in self.layers:
            x = layer.forward(x)

        # Step 4: Final normalization
        x = self.final_norm.forward(x)

        return x


# ==============================================================================
# DEMO: Simple sequence task
# ==============================================================================


def demo_attention_patterns():
    """
    Demonstrate attention patterns on a simple sequence.
    
    Task: Show how attention weights reveal which tokens attend to which.
    This is a forward-pass-only demo (no training) to illustrate the mechanics.
    """
    print("=" * 70)
    print("DEMO: Transformer Attention Mechanism Visualization")
    print("=" * 70)

    # Hyperparameters (small for visualization)
    d_model = 16    # Embedding dimension
    n_heads = 4     # Number of attention heads
    d_ff = 32       # Feed-forward hidden dimension
    seq_len = 5     # Sequence length
    vocab_size = 20 # Vocabulary size

    np.random.seed(42)  # Reproducibility

    # Create a mini transformer encoder
    encoder = TransformerEncoder(
        vocab_size=vocab_size,
        d_model=d_model,
        n_heads=n_heads,
        d_ff=d_ff,
        n_layers=2,
        max_seq_len=100
    )

    # Simulate input: batch of 1 sequence with 5 tokens
    token_ids = np.array([[3, 7, 12, 7, 1]])  # Note: token 7 appears twice
    print(f"\nInput token IDs: {token_ids[0]}")
    print(f"(Token 7 appears at positions 1 and 3 — watch if attention links them)\n")

    # Forward pass
    output = encoder.forward(token_ids)
    print(f"Output shape: {output.shape}  (batch=1, seq_len=5, d_model=16)")
    print(f"Output (first 4 dims of each token):")
    for i in range(seq_len):
        print(f"  Position {i} (token {token_ids[0][i]}): {output[0, i, :4].round(3)}")

    # Show attention weights from the first layer
    print("\n" + "-" * 70)
    print("Attention weights (Layer 1, Head 1):")
    print("-" * 70)

    # Re-run just the attention to get weights
    x = encoder.token_embedding[token_ids] * np.sqrt(d_model)
    x = x + encoder.pos_encoding.forward(seq_len)
    normed = encoder.layers[0].norm1.forward(x)
    _, attn_weights = encoder.layers[0].attention.forward(normed, normed, normed)

    # Display attention matrix for head 0
    head_0_attn = attn_weights[0, 0]  # [seq_len, seq_len]
    print("\n  From\\To  ", end="")
    for i in range(seq_len):
        print(f"  pos{i}", end="")
    print()
    for i in range(seq_len):
        print(f"  pos{i}(t{token_ids[0][i]:2d})", end="")
        for j in range(seq_len):
            print(f"  {head_0_attn[i, j]:.2f}", end="")
        print()

    print("\n(Values show how much each row-token attends to each column-token)")
    print("(Rows sum to 1.0 — it's a probability distribution)")


def demo_positional_encoding():
    """Visualize positional encoding patterns."""
    print("\n" + "=" * 70)
    print("DEMO: Positional Encoding Patterns")
    print("=" * 70)

    pe = PositionalEncoding(d_model=8, max_len=20)
    encoding = pe.forward(10)

    print("\nPositional encodings for positions 0-9, dimensions 0-7:")
    print("(Notice: low dims oscillate fast, high dims oscillate slowly)\n")
    print("  Pos  dim0   dim1   dim2   dim3   dim4   dim5   dim6   dim7")
    for pos in range(10):
        vals = " ".join(f"{v:6.3f}" for v in encoding[pos])
        print(f"  {pos:3d}  {vals}")

    # Show that relative positions are learnable
    print("\n  Key property: PE(pos+1) - PE(pos) is roughly constant across positions")
    print("  (This is what allows the model to learn relative positioning)")
    diffs = encoding[1:] - encoding[:-1]
    print(f"  Diff[0→1]: {diffs[0, :4].round(3)}")
    print(f"  Diff[4→5]: {diffs[4, :4].round(3)}")
    print(f"  Diff[8→9]: {diffs[8, :4].round(3)}")


def demo_causal_mask():
    """Demonstrate causal (autoregressive) masking."""
    print("\n" + "=" * 70)
    print("DEMO: Causal Mask for Decoder Self-Attention")
    print("=" * 70)

    seq_len = 5
    # Lower triangular matrix: position i can attend to positions 0..i
    causal_mask = np.tril(np.ones((seq_len, seq_len)))

    print(f"\nCausal mask ({seq_len}×{seq_len}):")
    print("(1 = can attend, 0 = blocked / set to -inf before softmax)\n")
    for i in range(seq_len):
        print(f"  Token {i}: {causal_mask[i].astype(int)}")

    print("\n  Token 0 can only see itself (no cheating!)")
    print("  Token 4 can see all previous tokens (full context)")
    print("\n  This enforces autoregressive property: P(xₜ | x₁,...,xₜ₋₁)")

    # Show effect on attention
    np.random.seed(0)
    d_k = 4
    Q = np.random.randn(1, seq_len, d_k)
    K = np.random.randn(1, seq_len, d_k)
    V = np.random.randn(1, seq_len, d_k)

    # Without mask
    out_no_mask, weights_no_mask = scaled_dot_product_attention(Q, K, V)
    # With mask
    out_masked, weights_masked = scaled_dot_product_attention(Q, K, V, causal_mask)

    print("\n  Attention weights WITHOUT mask (token 0 row):")
    print(f"    {weights_no_mask[0, 0].round(3)}")
    print("  Attention weights WITH causal mask (token 0 row):")
    print(f"    {weights_masked[0, 0].round(3)}")
    print("  → With mask, token 0 puts ALL weight on itself (can't see future)")


# ==============================================================================
# MAIN
# ==============================================================================


if __name__ == "__main__":
    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║   TRANSFORMER ENCODER — Complete NumPy Implementation               ║")
    print("║   Educational reference for Staff Architect level understanding     ║")
    print("╚══════════════════════════════════════════════════════════════════════╝")

    demo_positional_encoding()
    demo_causal_mask()
    demo_attention_patterns()

    print("\n" + "=" * 70)
    print("KEY TAKEAWAYS:")
    print("=" * 70)
    print("""
    1. Attention is just: weighted sum of values, where weights come from
       query-key similarity (dot product → softmax).

    2. Multi-head splits the representation space so different heads can
       learn different relationship types in parallel.

    3. Positional encoding uses sinusoids at different frequencies —
       like a Fourier basis for position.

    4. LayerNorm + residual connections are essential for training stability
       in deep networks.

    5. The feed-forward network (expand → activate → contract) is where
       per-token "reasoning" happens; attention just routes information.

    6. Causal masking prevents future information leakage in decoders,
       enforcing the autoregressive property needed for generation.

    7. Scaling by √d_k keeps dot products in a reasonable range,
       preventing softmax saturation and gradient vanishing.
    """)
