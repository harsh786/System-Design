"""
Attention Mechanism Visualizer
==============================
Simulates transformer attention mechanisms in pure Python.
Demonstrates Q, K, V computation, attention scores, and compares
MHA vs MQA vs GQA memory usage.

No external dependencies required - standard library only.
"""

import math
import random

# ============================================================
# SECTION 1: Basic Linear Algebra Helpers
# ============================================================

def mat_zeros(rows, cols):
    """Create a zero matrix."""
    return [[0.0] * cols for _ in range(rows)]


def mat_rand(rows, cols, seed=42):
    """Create a random matrix with small values."""
    rng = random.Random(seed)
    return [[rng.gauss(0, 0.5) for _ in range(cols)] for _ in range(rows)]


def mat_mul(A, B):
    """Multiply two matrices."""
    rows_a, cols_a = len(A), len(A[0])
    rows_b, cols_b = len(B), len(B[0])
    assert cols_a == rows_b, f"Shape mismatch: {cols_a} != {rows_b}"
    C = mat_zeros(rows_a, cols_b)
    for i in range(rows_a):
        for j in range(cols_b):
            s = 0.0
            for k in range(cols_a):
                s += A[i][k] * B[k][j]
            C[i][j] = s
    return C


def mat_transpose(A):
    """Transpose a matrix."""
    rows, cols = len(A), len(A[0])
    return [[A[i][j] for i in range(rows)] for j in range(cols)]


def softmax(row):
    """Softmax over a list of values."""
    max_val = max(row)
    exps = [math.exp(x - max_val) for x in row]
    total = sum(exps)
    return [e / total for e in exps]


# ============================================================
# SECTION 2: Self-Attention Implementation
# ============================================================

def scaled_dot_product_attention(Q, K, V, mask=None):
    """
    Compute scaled dot-product attention.
    
    attention(Q, K, V) = softmax(Q @ K^T / sqrt(d_k)) @ V
    """
    d_k = len(K[0])
    scale = math.sqrt(d_k)
    
    # Q @ K^T
    K_T = mat_transpose(K)
    scores = mat_mul(Q, K_T)
    
    # Scale
    seq_len = len(scores)
    for i in range(seq_len):
        for j in range(len(scores[0])):
            scores[i][j] /= scale
    
    # Optional causal mask
    if mask:
        for i in range(seq_len):
            for j in range(len(scores[0])):
                if j > i:
                    scores[i][j] = -1e9
    
    # Softmax per row
    attention_weights = [softmax(row) for row in scores]
    
    # Weighted sum of values
    output = mat_mul(attention_weights, V)
    
    return output, attention_weights


def self_attention_forward(X, W_q, W_k, W_v, causal=True):
    """
    Full self-attention forward pass.
    
    X: input embeddings [seq_len, d_model]
    W_q, W_k, W_v: weight matrices [d_model, d_head]
    """
    Q = mat_mul(X, W_q)
    K = mat_mul(X, W_k)
    V = mat_mul(X, W_v)
    
    output, weights = scaled_dot_product_attention(Q, K, V, mask=causal)
    return output, weights, Q, K, V


# ============================================================
# SECTION 3: ASCII Heatmap Visualization
# ============================================================

HEATMAP_CHARS = " ░▒▓█"


def ascii_heatmap(matrix, row_labels=None, col_labels=None, title=""):
    """Render a matrix as an ASCII heatmap."""
    if title:
        print(f"\n{'=' * 60}")
        print(f"  {title}")
        print(f"{'=' * 60}")
    
    # Find min/max for normalization
    flat = [v for row in matrix for v in row]
    min_val, max_val = min(flat), max(flat)
    val_range = max_val - min_val if max_val != min_val else 1.0
    
    rows = len(matrix)
    cols = len(matrix[0])
    
    # Column headers
    if col_labels:
        header = "        " + "".join(f"{l:>6}" for l in col_labels[:cols])
        print(header)
        print("        " + "-" * (cols * 6))
    
    for i in range(rows):
        label = f"{row_labels[i]:>6} |" if row_labels else f"{i:>6} |"
        cells = ""
        for j in range(cols):
            normalized = (matrix[i][j] - min_val) / val_range
            char_idx = min(int(normalized * (len(HEATMAP_CHARS) - 1)), len(HEATMAP_CHARS) - 1)
            char = HEATMAP_CHARS[char_idx]
            cells += f"  {char}{char}{char} "
        print(f"{label}{cells}")
    
    # Legend
    print(f"\n  Legend: [' '=0.0] ['░'=0.25] ['▒'=0.5] ['▓'=0.75] ['█'=1.0]")


def print_matrix(matrix, name="Matrix", precision=3):
    """Pretty-print a matrix with values."""
    print(f"\n  {name} ({len(matrix)}×{len(matrix[0])}):")
    for i, row in enumerate(matrix):
        values = " ".join(f"{v:>7.{precision}f}" for v in row)
        print(f"    [{values}]")


# ============================================================
# SECTION 4: Multi-Head Attention Comparison
# ============================================================

def compute_kv_cache_size(
    num_layers,
    seq_len,
    d_model,
    num_kv_heads,
    bytes_per_param=2  # BF16
):
    """
    Compute KV cache size in bytes.
    
    KV cache stores K and V for each layer.
    Size = 2 × layers × seq_len × (d_model / num_heads × num_kv_heads) × bytes
    """
    d_head = d_model // num_kv_heads  # This simplification works for our comparison
    # Actually: d_head = d_model // num_attention_heads, and we store num_kv_heads of them
    # Let's be more precise:
    head_dim = 128  # typical for modern models
    size = 2 * num_layers * seq_len * num_kv_heads * head_dim * bytes_per_param
    return size


def compare_attention_variants():
    """Compare MHA, MQA, and GQA memory usage."""
    print("\n" + "=" * 70)
    print("  ATTENTION VARIANT COMPARISON: MHA vs MQA vs GQA")
    print("=" * 70)
    
    print("""
  Multi-Head Attention (MHA):
    - Each head has its OWN K and V projections
    - Maximum expressiveness
    - Maximum memory usage
    
  Multi-Query Attention (MQA):
    - ALL heads share ONE K and ONE V projection
    - Minimal KV cache (1/num_heads reduction)
    - Slight quality loss
    
  Grouped-Query Attention (GQA):
    - Heads are grouped; each GROUP shares K and V
    - Balance between MHA and MQA
    - Used in LLaMA-2 70B, LLaMA-3, Mistral
  """)
    
    # Model configurations to compare
    configs = [
        {
            "name": "LLaMA-3 8B (GQA)",
            "layers": 32,
            "d_model": 4096,
            "num_heads": 32,
            "num_kv_heads_mha": 32,
            "num_kv_heads_gqa": 8,
            "num_kv_heads_mqa": 1,
        },
        {
            "name": "LLaMA-3 70B (GQA)",
            "layers": 80,
            "d_model": 8192,
            "num_heads": 64,
            "num_kv_heads_mha": 64,
            "num_kv_heads_gqa": 8,
            "num_kv_heads_mqa": 1,
        },
        {
            "name": "GPT-4 scale (estimated)",
            "layers": 120,
            "d_model": 12288,
            "num_heads": 96,
            "num_kv_heads_mha": 96,
            "num_kv_heads_gqa": 12,
            "num_kv_heads_mqa": 1,
        },
    ]
    
    context_lengths = [4096, 32768, 131072]
    
    print(f"\n  {'Model':<28} {'Context':<10} {'MHA':>12} {'GQA':>12} {'MQA':>12} {'GQA Savings':>12}")
    print(f"  {'-'*28} {'-'*10} {'-'*12} {'-'*12} {'-'*12} {'-'*12}")
    
    for config in configs:
        for ctx_len in context_lengths:
            head_dim = config["d_model"] // config["num_heads"]
            
            mha_size = 2 * config["layers"] * ctx_len * config["num_kv_heads_mha"] * head_dim * 2
            gqa_size = 2 * config["layers"] * ctx_len * config["num_kv_heads_gqa"] * head_dim * 2
            mqa_size = 2 * config["layers"] * ctx_len * config["num_kv_heads_mqa"] * head_dim * 2
            
            savings = (1 - gqa_size / mha_size) * 100
            
            def fmt_bytes(b):
                if b >= 1024**3:
                    return f"{b/1024**3:.1f} GB"
                elif b >= 1024**2:
                    return f"{b/1024**2:.1f} MB"
                else:
                    return f"{b/1024:.1f} KB"
            
            print(f"  {config['name']:<28} {ctx_len:<10} {fmt_bytes(mha_size):>12} "
                  f"{fmt_bytes(gqa_size):>12} {fmt_bytes(mqa_size):>12} {savings:>10.0f}%")
        print()


# ============================================================
# SECTION 5: Quadratic Scaling Demonstration
# ============================================================

def demonstrate_quadratic_scaling():
    """Show how attention memory scales with sequence length."""
    print("\n" + "=" * 70)
    print("  QUADRATIC MEMORY SCALING WITH CONTEXT LENGTH")
    print("=" * 70)
    
    print("""
  Attention score matrix is [seq_len × seq_len].
  Memory for attention = seq_len² × num_heads × bytes_per_element
  
  This is why long context is expensive!
  """)
    
    d_model = 4096
    num_heads = 32
    bytes_per_element = 2  # BF16
    
    print(f"  Model: d_model={d_model}, heads={num_heads}, BF16")
    print(f"\n  {'Context Length':<16} {'Attention Memory':<20} {'Relative':>10} {'Bar'}")
    print(f"  {'-'*16} {'-'*20} {'-'*10} {'-'*30}")
    
    base_mem = None
    lengths = [512, 1024, 2048, 4096, 8192, 16384, 32768, 65536, 131072]
    
    for seq_len in lengths:
        # Memory for attention scores: seq_len² × num_heads × bytes
        mem = seq_len * seq_len * num_heads * bytes_per_element
        
        if base_mem is None:
            base_mem = mem
        
        relative = mem / base_mem
        
        if mem >= 1024**3:
            mem_str = f"{mem/1024**3:.1f} GB"
        elif mem >= 1024**2:
            mem_str = f"{mem/1024**2:.1f} MB"
        else:
            mem_str = f"{mem/1024:.1f} KB"
        
        bar_len = min(int(math.log2(relative) * 3) + 1, 40)
        bar = "█" * bar_len
        
        print(f"  {seq_len:<16} {mem_str:<20} {relative:>8.0f}× {bar}")
    
    print("""
  Key insight: Going from 4K → 128K context is 1024× more attention memory.
  This is why techniques like:
    - Flash Attention (IO-aware, same math, less memory transfers)
    - Sliding window attention (limit attention span)
    - Ring attention (distribute across GPUs)
    - SSMs (O(n) alternative)
  ...are critical for long-context models.
  """)


# ============================================================
# SECTION 6: Educational Step-by-Step Demo
# ============================================================

def educational_attention_demo():
    """Walk through attention computation step by step."""
    print("=" * 70)
    print("  SELF-ATTENTION: STEP-BY-STEP WALKTHROUGH")
    print("=" * 70)
    
    # Small example: 4 tokens, 3-dimensional embeddings
    tokens = ["The", "cat", "sat", "down"]
    seq_len = 4
    d_model = 3
    d_head = 3
    
    print(f"\n  Input: \"{' '.join(tokens)}\"")
    print(f"  Sequence length: {seq_len}, Embedding dim: {d_model}")
    
    # Random but reproducible embeddings
    random.seed(42)
    X = [[random.gauss(0, 1) for _ in range(d_model)] for _ in range(seq_len)]
    
    print("\n  Step 1: Input Embeddings (X)")
    print("  Each token is represented as a vector:")
    for i, token in enumerate(tokens):
        vals = " ".join(f"{v:>6.3f}" for v in X[i])
        print(f"    {token:>5}: [{vals}]")
    
    # Weight matrices
    W_q = mat_rand(d_model, d_head, seed=100)
    W_k = mat_rand(d_model, d_head, seed=200)
    W_v = mat_rand(d_model, d_head, seed=300)
    
    print("\n  Step 2: Compute Q = X @ W_q, K = X @ W_k, V = X @ W_v")
    print("  (Each token gets its own Query, Key, and Value vector)")
    
    Q = mat_mul(X, W_q)
    K = mat_mul(X, W_k)
    V = mat_mul(X, W_v)
    
    print_matrix(Q, "Q (Queries) - 'What am I looking for?'")
    print_matrix(K, "K (Keys) - 'What do I contain?'")
    print_matrix(V, "V (Values) - 'What information do I provide?'")
    
    print(f"\n  Step 3: Compute attention scores = Q @ K^T / sqrt(d_k)")
    print(f"  Scale factor: sqrt({d_head}) = {math.sqrt(d_head):.3f}")
    
    K_T = mat_transpose(K)
    raw_scores = mat_mul(Q, K_T)
    scale = math.sqrt(d_head)
    scaled_scores = [[v / scale for v in row] for row in raw_scores]
    
    print_matrix(scaled_scores, "Scaled Attention Scores")
    
    print("\n  Step 4: Apply causal mask (prevent attending to future tokens)")
    masked_scores = [row[:] for row in scaled_scores]
    for i in range(seq_len):
        for j in range(seq_len):
            if j > i:
                masked_scores[i][j] = float('-inf')
    
    print("  (Positions where j > i are set to -inf)")
    
    print("\n  Step 5: Apply softmax (normalize to probabilities)")
    attention_weights = []
    for row in masked_scores:
        finite_row = [v if v != float('-inf') else -1e9 for v in row]
        attention_weights.append(softmax(finite_row))
    
    print_matrix(attention_weights, "Attention Weights (after softmax)")
    
    # ASCII heatmap
    ascii_heatmap(
        attention_weights,
        row_labels=tokens,
        col_labels=tokens,
        title="ATTENTION PATTERN (who attends to whom)"
    )
    
    print("""
  Reading the heatmap:
    - Row = the token doing the "looking" (query)
    - Column = the token being "looked at" (key)
    - 'The' can only attend to itself (first token)
    - 'cat' attends to 'The' and itself
    - 'down' can attend to all previous tokens
  """)
    
    print("  Step 6: Compute output = attention_weights @ V")
    output = mat_mul(attention_weights, V)
    print_matrix(output, "Output (weighted combination of Values)")
    
    print("""
  Each output row is a weighted sum of Value vectors,
  where weights are determined by Query-Key compatibility.
  This is how transformers "mix" information across positions.
  """)


# ============================================================
# MAIN
# ============================================================

def main():
    print("\n" + "╔" + "═" * 68 + "╗")
    print("║" + " ATTENTION MECHANISM VISUALIZER ".center(68) + "║")
    print("║" + " Understanding Transformer Attention from First Principles ".center(68) + "║")
    print("╚" + "═" * 68 + "╝")
    
    # Part 1: Educational walkthrough
    educational_attention_demo()
    
    # Part 2: Compare attention variants
    compare_attention_variants()
    
    # Part 3: Quadratic scaling
    demonstrate_quadratic_scaling()
    
    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print("""
  Key Takeaways:
  
  1. Attention computes pairwise compatibility between all token positions
  2. Q (query) asks "what am I looking for?"
     K (key) says "what do I contain?"  
     V (value) says "here's my information"
  3. Causal mask prevents tokens from attending to future positions
  4. GQA reduces KV cache by 4-8× with minimal quality loss
  5. Attention memory scales O(n²) — the fundamental bottleneck
  6. Flash Attention doesn't change the math, just the memory access pattern
  """)


if __name__ == "__main__":
    main()
