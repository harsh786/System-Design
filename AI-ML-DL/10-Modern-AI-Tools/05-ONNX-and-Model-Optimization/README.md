# ONNX and Model Optimization

## Why Model Optimization Matters

```
Training (GPU, batch) → Inference (latency-sensitive, cost-sensitive)

Unoptimized:  100ms/request, $10k/month GPU costs
Optimized:    10ms/request,  $1k/month (or CPU-only)

Edge deployment: Must fit in <500MB RAM, run on mobile/IoT
```

```
┌─────────────────────────────────────────────────────────────────┐
│                  Model Optimization Pipeline                      │
├─────────────────────────────────────────────────────────────────┤
│  Training Framework  →  Export  →  Optimize  →  Deploy           │
│  (PyTorch/TF)           (ONNX)    (Quant/Prune) (Runtime)       │
├─────────────────────────────────────────────────────────────────┤
│  Target Runtimes:                                                │
│  ├── ONNX Runtime (cross-platform)                               │
│  ├── TensorRT (NVIDIA GPUs)                                      │
│  ├── OpenVINO (Intel CPUs/GPUs)                                  │
│  ├── CoreML (Apple devices)                                      │
│  ├── TFLite (Android/embedded)                                   │
│  └── vLLM / TGI (LLM-specific)                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Installation

```bash
pip install onnx onnxruntime onnxruntime-gpu  # ONNX ecosystem
pip install optimum[onnxruntime]               # HuggingFace ONNX integration
pip install tensorrt                           # NVIDIA TensorRT
pip install openvino openvino-dev              # Intel OpenVINO
pip install vllm                               # LLM inference
```

---

## ONNX (Open Neural Network Exchange)

### Export from PyTorch

```python
import torch
import onnx

# Simple model export
model = MyModel()
model.eval()

dummy_input = torch.randn(1, 3, 224, 224)

torch.onnx.export(
    model,
    dummy_input,
    "model.onnx",
    input_names=["input"],
    output_names=["output"],
    dynamic_axes={
        "input": {0: "batch_size"},     # Variable batch size
        "output": {0: "batch_size"},
    },
    opset_version=17,
)

# Validate exported model
model = onnx.load("model.onnx")
onnx.checker.check_model(model)
print(onnx.helper.printable_graph(model.graph))
```

### Export HuggingFace Models (Easy Way)

```python
from optimum.onnxruntime import ORTModelForSequenceClassification
from transformers import AutoTokenizer

# Export and load in one step
model = ORTModelForSequenceClassification.from_pretrained(
    "distilbert-base-uncased-finetuned-sst-2-english",
    export=True,  # Automatically exports to ONNX
)
tokenizer = AutoTokenizer.from_pretrained("distilbert-base-uncased-finetuned-sst-2-english")

# Use exactly like transformers
inputs = tokenizer("This is great!", return_tensors="np")
outputs = model(**inputs)

# Or use CLI
# optimum-cli export onnx --model bert-base-uncased bert-onnx/
```

### ONNX Runtime Inference

```python
import onnxruntime as ort
import numpy as np

# Create session with optimizations
session_options = ort.SessionOptions()
session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
session_options.intra_op_num_threads = 4

# CPU inference
session = ort.InferenceSession(
    "model.onnx",
    sess_options=session_options,
    providers=["CPUExecutionProvider"],
)

# GPU inference
session = ort.InferenceSession(
    "model.onnx",
    providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
)

# Run inference
input_name = session.get_inputs()[0].name
output_name = session.get_outputs()[0].name
result = session.run([output_name], {input_name: input_data.numpy()})[0]

# Benchmark
import time
times = []
for _ in range(100):
    start = time.perf_counter()
    session.run([output_name], {input_name: input_data.numpy()})
    times.append(time.perf_counter() - start)

print(f"Mean: {np.mean(times)*1000:.2f}ms, P95: {np.percentile(times, 95)*1000:.2f}ms")
```

---

## Quantization

### Dynamic Quantization (Easiest)

```python
from onnxruntime.quantization import quantize_dynamic, QuantType

quantize_dynamic(
    model_input="model.onnx",
    model_output="model_int8.onnx",
    weight_type=QuantType.QInt8,
)
# Typically 2-4x faster on CPU, <1% accuracy loss
```

### Static Quantization (More Accurate)

```python
from onnxruntime.quantization import quantize_static, CalibrationDataReader

class MyCalibrationReader(CalibrationDataReader):
    def __init__(self, calibration_data):
        self.data = iter(calibration_data)

    def get_next(self):
        try:
            return {"input": next(self.data)}
        except StopIteration:
            return None

# Needs representative calibration data (100-1000 samples)
calibration_data = [np.random.randn(1, 3, 224, 224).astype(np.float32) for _ in range(100)]
reader = MyCalibrationReader(calibration_data)

quantize_static(
    model_input="model.onnx",
    model_output="model_static_int8.onnx",
    calibration_data_reader=reader,
)
```

### HuggingFace Optimum Quantization

```python
from optimum.onnxruntime import ORTQuantizer
from optimum.onnxruntime.configuration import AutoQuantizationConfig

quantizer = ORTQuantizer.from_pretrained("./onnx-model")
qconfig = AutoQuantizationConfig.avx512_vnni(is_static=False, per_channel=True)
quantizer.quantize(save_dir="./quantized-model", quantization_config=qconfig)
```

---

## Pruning

```python
import torch
import torch.nn.utils.prune as prune

model = MyModel()

# Unstructured pruning (zero out individual weights)
for name, module in model.named_modules():
    if isinstance(module, torch.nn.Linear):
        prune.l1_unstructured(module, name="weight", amount=0.3)  # Remove 30%

# Structured pruning (remove entire channels/neurons)
for name, module in model.named_modules():
    if isinstance(module, torch.nn.Conv2d):
        prune.ln_structured(module, name="weight", amount=0.2, n=2, dim=0)

# Make pruning permanent
for name, module in model.named_modules():
    if isinstance(module, (torch.nn.Linear, torch.nn.Conv2d)):
        prune.remove(module, "weight")

# Check sparsity
total = sum(p.numel() for p in model.parameters())
zeros = sum((p == 0).sum().item() for p in model.parameters())
print(f"Sparsity: {zeros/total*100:.1f}%")
```

---

## Knowledge Distillation

```python
import torch
import torch.nn.functional as F

teacher = LargeModel()  # Pre-trained, frozen
student = SmallModel()  # To be trained

teacher.eval()
temperature = 4.0
alpha = 0.7  # Weight for distillation loss

for data, labels in train_loader:
    # Student predictions
    student_logits = student(data)

    # Teacher predictions (no grad needed)
    with torch.no_grad():
        teacher_logits = teacher(data)

    # Distillation loss (soft targets)
    distill_loss = F.kl_div(
        F.log_softmax(student_logits / temperature, dim=1),
        F.softmax(teacher_logits / temperature, dim=1),
        reduction="batchmean",
    ) * (temperature ** 2)

    # Hard label loss
    hard_loss = F.cross_entropy(student_logits, labels)

    # Combined loss
    loss = alpha * distill_loss + (1 - alpha) * hard_loss
    loss.backward()
    optimizer.step()
    optimizer.zero_grad()
```

---

## TensorRT (NVIDIA GPUs)

```python
import tensorrt as trt
import pycuda.driver as cuda

# Convert ONNX to TensorRT
logger = trt.Logger(trt.Logger.WARNING)
builder = trt.Builder(logger)
network = builder.create_network(1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH))
parser = trt.OnnxParser(network, logger)

with open("model.onnx", "rb") as f:
    parser.parse(f.read())

config = builder.create_builder_config()
config.set_memory_pool_limit(trt.MemoryPoolType.WORKSPACE, 1 << 30)  # 1GB
config.set_flag(trt.BuilderFlag.FP16)  # Enable FP16

engine = builder.build_serialized_network(network, config)
with open("model.trt", "wb") as f:
    f.write(engine)

# Typical speedup: 2-5x over PyTorch, 1.5-3x over ONNX Runtime
```

---

## vLLM (LLM-Specific Inference)

```python
from vllm import LLM, SamplingParams

# Initialize (handles PagedAttention, continuous batching)
llm = LLM(
    model="meta-llama/Llama-2-7b-chat-hf",
    tensor_parallel_size=2,       # Multi-GPU
    dtype="float16",
    max_model_len=4096,
    gpu_memory_utilization=0.9,
)

# Batch inference
prompts = ["What is AI?", "Explain quantum computing", "Write a poem"]
sampling_params = SamplingParams(temperature=0.7, top_p=0.9, max_tokens=256)

outputs = llm.generate(prompts, sampling_params)
for output in outputs:
    print(output.outputs[0].text)

# Start OpenAI-compatible server
# python -m vllm.entrypoints.openai.api_server --model meta-llama/Llama-2-7b-chat-hf
```

---

## Latency Comparison Table

| Runtime | Hardware | BERT (batch=1) | ResNet50 (batch=1) | LLaMA-7B (tok/s) |
|---------|----------|---------------|--------------------|--------------------|
| PyTorch FP32 | CPU | 45ms | 35ms | N/A |
| PyTorch FP32 | GPU | 8ms | 5ms | 30 |
| ONNX Runtime | CPU | 15ms | 12ms | N/A |
| ONNX Runtime | GPU | 4ms | 3ms | 45 |
| ONNX INT8 | CPU | 8ms | 6ms | N/A |
| TensorRT FP16 | GPU | 2ms | 1.5ms | 60 |
| OpenVINO | Intel CPU | 10ms | 8ms | N/A |
| vLLM | GPU | N/A | N/A | 100+ |

*Approximate values - actual results depend on hardware and model*

---

## Optimization Decision Tree

```
Is it an LLM?
├── Yes → vLLM or TGI (PagedAttention, continuous batching)
│         └── Need quantization? → GPTQ, AWQ, or bitsandbytes
└── No → What's the target?
    ├── NVIDIA GPU → TensorRT (best perf) or ONNX Runtime CUDA
    ├── Intel CPU → OpenVINO
    ├── Apple → CoreML (via coremltools)
    ├── Android → TFLite
    ├── Cross-platform → ONNX Runtime
    └── Web browser → ONNX Runtime Web or TF.js

Always try in order:
1. ONNX export + ONNX Runtime (easy, good gains)
2. Quantization (INT8 dynamic - nearly free accuracy)
3. Hardware-specific runtime (TensorRT, OpenVINO)
4. Pruning / Distillation (when above isn't enough)
```

---

## Complete Optimization Pipeline

```python
# 1. Train model normally
model = train_model()

# 2. Export to ONNX
torch.onnx.export(model, dummy_input, "model.onnx", opset_version=17,
                  dynamic_axes={"input": {0: "batch"}, "output": {0: "batch"}})

# 3. Optimize graph
from onnxruntime.transformers import optimizer
optimized = optimizer.optimize_model("model.onnx", model_type="bert")
optimized.save_model_to_file("model_optimized.onnx")

# 4. Quantize
from onnxruntime.quantization import quantize_dynamic, QuantType
quantize_dynamic("model_optimized.onnx", "model_int8.onnx", weight_type=QuantType.QInt8)

# 5. Benchmark
import onnxruntime as ort, time, numpy as np
session = ort.InferenceSession("model_int8.onnx")
times = [time.perf_counter() for _ in range(101)]  # warmup + 100 runs
for i in range(100):
    session.run(None, {"input": sample_input})
    times[i+1] = time.perf_counter()
latencies = [times[i+1]-times[i] for i in range(100)]
print(f"P50: {np.percentile(latencies,50)*1000:.1f}ms  P99: {np.percentile(latencies,99)*1000:.1f}ms")

# 6. Validate accuracy
original_acc = evaluate(original_model, test_set)
optimized_acc = evaluate_onnx(session, test_set)
print(f"Accuracy drop: {original_acc - optimized_acc:.4f}")
```

---

## Common Pitfalls

1. **Not using dynamic axes**: Fixed batch size prevents batching flexibility
2. **Skipping validation**: Always compare accuracy before/after optimization
3. **Wrong opset version**: Use opset 17+ for modern ops support
4. **Ignoring warmup**: First inference is slow (JIT compilation) - exclude from benchmarks
5. **Quantizing everything**: Some layers (first/last) should stay FP32 for accuracy

## Best Practices

- Always benchmark end-to-end (including pre/post processing)
- Start with easiest optimization (ONNX export), measure, then go deeper
- Keep original model for accuracy validation
- Use dynamic axes for production flexibility
- Profile before optimizing - find the actual bottleneck
- Test with representative data, not random tensors
- Monitor accuracy in production (quantization can cause drift on edge cases)
