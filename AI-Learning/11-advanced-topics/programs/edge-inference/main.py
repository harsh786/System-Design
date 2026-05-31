"""
Edge Inference Demonstration

Compares full-precision vs quantized model inference to show
the trade-offs of edge deployment:
- Speed: How much faster is the quantized model?
- Memory: How much less RAM does it need?
- Accuracy: How much quality do we lose?

This simulates edge constraints (limited memory, CPU-only)
to demonstrate why quantization matters for on-device AI.
"""

import time
import os
import sys
import traceback

import numpy as np
import torch
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    pipeline,
)

# Suppress warnings for cleaner output
os.environ["TOKENIZERS_PARALLELISM"] = "false"
import warnings
warnings.filterwarnings("ignore")


def get_model_size_mb(model) -> float:
    """Calculate model size in MB by summing parameter memory."""
    param_size = sum(p.nelement() * p.element_size() for p in model.parameters())
    buffer_size = sum(b.nelement() * b.element_size() for b in model.buffers())
    return (param_size + buffer_size) / (1024 * 1024)


def get_memory_usage_mb() -> float:
    """Get current process memory usage."""
    import resource
    # Returns max resident set size in bytes (macOS) or KB (Linux)
    rusage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return rusage / (1024 * 1024)  # bytes to MB on macOS
    return rusage / 1024  # KB to MB on Linux


def benchmark_inference(pipe, texts: list[str], num_runs: int = 3) -> dict:
    """
    Benchmark a model pipeline.
    
    Returns timing statistics and predictions.
    """
    # Warmup
    _ = pipe(texts[0])
    
    # Timed runs
    latencies = []
    predictions = []
    
    for run in range(num_runs):
        for text in texts:
            start = time.perf_counter()
            result = pipe(text)
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
            if run == 0:
                predictions.append(result[0])
    
    return {
        "avg_latency_ms": np.mean(latencies),
        "p50_latency_ms": np.median(latencies),
        "p95_latency_ms": np.percentile(latencies, 95),
        "min_latency_ms": np.min(latencies),
        "max_latency_ms": np.max(latencies),
        "predictions": predictions
    }


def quantize_model_dynamic(model):
    """
    Apply dynamic quantization (INT8) to the model.
    
    Dynamic quantization:
    - Weights are quantized (stored as INT8)
    - Activations are quantized on-the-fly during inference
    - No calibration data needed
    - Best for CPU inference
    """
    quantized_model = torch.quantization.quantize_dynamic(
        model,
        {torch.nn.Linear},  # Quantize all linear layers
        dtype=torch.qint8
    )
    return quantized_model


def main():
    print("\n" + "=" * 60)
    print("EDGE INFERENCE BENCHMARK")
    print("Comparing Full Precision (FP32) vs Quantized (INT8)")
    print("=" * 60)
    
    # --- Configuration ---
    model_name = "distilbert-base-uncased-finetuned-sst-2-english"
    
    # Test texts (sentiment classification)
    test_texts = [
        "This product is absolutely wonderful, I love it!",
        "The service was terrible and the staff was rude.",
        "It's okay, nothing special but not bad either.",
        "I'm extremely disappointed with the quality.",
        "Best purchase I've ever made, highly recommend!",
        "The delivery was fast and the packaging was great.",
        "Would not recommend this to anyone, waste of money.",
        "Decent value for the price, meets expectations.",
    ]
    
    print(f"\nModel: {model_name}")
    print(f"Task: Sentiment Classification")
    print(f"Test samples: {len(test_texts)}")
    print(f"Device: CPU (simulating edge constraints)")
    
    # --- Load Full Precision Model ---
    print("\n" + "-" * 40)
    print("[1/4] Loading full precision model (FP32)...")
    
    mem_before = get_memory_usage_mb()
    
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model_fp32 = AutoModelForSequenceClassification.from_pretrained(model_name)
    model_fp32.eval()  # Set to inference mode
    
    mem_after_fp32 = get_memory_usage_mb()
    model_size_fp32 = get_model_size_mb(model_fp32)
    
    print(f"  Model size: {model_size_fp32:.1f} MB")
    print(f"  Memory increase: {mem_after_fp32 - mem_before:.1f} MB")
    print(f"  Parameters: {sum(p.numel() for p in model_fp32.parameters()):,}")
    
    # --- Benchmark Full Precision ---
    print("\n[2/4] Benchmarking FP32 inference...")
    
    pipe_fp32 = pipeline(
        "sentiment-analysis",
        model=model_fp32,
        tokenizer=tokenizer,
        device=-1  # CPU only (simulating edge)
    )
    
    results_fp32 = benchmark_inference(pipe_fp32, test_texts)
    print(f"  Avg latency: {results_fp32['avg_latency_ms']:.1f} ms")
    print(f"  P95 latency: {results_fp32['p95_latency_ms']:.1f} ms")
    
    # --- Quantize Model ---
    print("\n[3/4] Quantizing model to INT8...")
    
    model_int8 = quantize_model_dynamic(model_fp32)
    model_size_int8 = get_model_size_mb(model_int8)
    
    print(f"  Quantized model size: {model_size_int8:.1f} MB")
    print(f"  Size reduction: {(1 - model_size_int8/model_size_fp32)*100:.1f}%")
    
    # --- Benchmark Quantized ---
    print("\n[4/4] Benchmarking INT8 inference...")
    
    pipe_int8 = pipeline(
        "sentiment-analysis",
        model=model_int8,
        tokenizer=tokenizer,
        device=-1
    )
    
    results_int8 = benchmark_inference(pipe_int8, test_texts)
    print(f"  Avg latency: {results_int8['avg_latency_ms']:.1f} ms")
    print(f"  P95 latency: {results_int8['p95_latency_ms']:.1f} ms")
    
    # --- Comparison Report ---
    print("\n" + "=" * 60)
    print("COMPARISON REPORT")
    print("=" * 60)
    
    speedup = results_fp32['avg_latency_ms'] / results_int8['avg_latency_ms']
    size_reduction = (1 - model_size_int8 / model_size_fp32) * 100
    
    print(f"""
┌─────────────────────┬──────────────┬──────────────┬──────────────┐
│ Metric              │ FP32         │ INT8         │ Improvement  │
├─────────────────────┼──────────────┼──────────────┼──────────────┤
│ Model Size          │ {model_size_fp32:>8.1f} MB │ {model_size_int8:>8.1f} MB │ {size_reduction:>8.1f}%  │
│ Avg Latency         │ {results_fp32['avg_latency_ms']:>8.1f} ms │ {results_int8['avg_latency_ms']:>8.1f} ms │ {speedup:>8.2f}x   │
│ P95 Latency         │ {results_fp32['p95_latency_ms']:>8.1f} ms │ {results_int8['p95_latency_ms']:>8.1f} ms │            │
│ Min Latency         │ {results_fp32['min_latency_ms']:>8.1f} ms │ {results_int8['min_latency_ms']:>8.1f} ms │            │
└─────────────────────┴──────────────┴──────────────┴──────────────┘
""")
    
    # Accuracy comparison
    print("PREDICTION COMPARISON (checking for accuracy degradation):")
    print("-" * 60)
    
    agreements = 0
    for i, (fp32_pred, int8_pred) in enumerate(
        zip(results_fp32['predictions'], results_int8['predictions'])
    ):
        match = "✓" if fp32_pred['label'] == int8_pred['label'] else "✗"
        if fp32_pred['label'] == int8_pred['label']:
            agreements += 1
        
        print(f"  {match} '{test_texts[i][:50]}...'")
        print(f"    FP32: {fp32_pred['label']} ({fp32_pred['score']:.4f})")
        print(f"    INT8: {int8_pred['label']} ({int8_pred['score']:.4f})")
    
    accuracy = agreements / len(test_texts) * 100
    print(f"\nAgreement rate: {accuracy:.0f}% ({agreements}/{len(test_texts)} match)")
    
    # --- Edge Deployment Summary ---
    print("\n" + "=" * 60)
    print("EDGE DEPLOYMENT IMPLICATIONS")
    print("=" * 60)
    print(f"""
For a device with 4 GB RAM (typical smartphone):
  FP32 model: Uses {model_size_fp32:.0f} MB ({model_size_fp32/4096*100:.1f}% of available RAM)
  INT8 model: Uses {model_size_int8:.0f} MB ({model_size_int8/4096*100:.1f}% of available RAM)

For real-time requirements (< 100ms latency):
  FP32: {'✓ Meets' if results_fp32['p95_latency_ms'] < 100 else '✗ Exceeds'} target ({results_fp32['p95_latency_ms']:.0f}ms P95)
  INT8: {'✓ Meets' if results_int8['p95_latency_ms'] < 100 else '✗ Exceeds'} target ({results_int8['p95_latency_ms']:.0f}ms P95)

Battery impact (relative compute):
  FP32: Baseline (1.0x compute)
  INT8: ~{1/speedup:.1f}x compute (longer battery life)

Conclusion: INT8 quantization gives {speedup:.1f}x speedup with {size_reduction:.0f}% 
less memory at {accuracy:.0f}% prediction agreement. This is the standard 
trade-off for edge deployment.
""")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nError: {e}")
        print("\nIf you see import errors, install dependencies:")
        print("  pip install -r requirements.txt")
        traceback.print_exc()
