# Edge and On-Device AI

## What is Edge AI?

**Edge AI** means running AI models directly on devices (phones, laptops, IoT sensors, cars) instead of sending data to the cloud.

**Analogy:** Cloud AI is like mailing a letter to get advice — you send your question, wait for delivery, wait for a response, wait for return delivery. Edge AI is like having an advisor sitting next to you — instant answers, no mailing needed.

```mermaid
flowchart LR
    subgraph Cloud AI
        A[Device] -->|Send data| B[Internet]
        B --> C[Cloud GPU]
        C -->|Send result| B
        B -->|Return| A
    end
    
    subgraph Edge AI
        D[Device with Model] -->|Instant| E[Result]
    end
```

---

## Why Edge AI?

| Benefit | Explanation | Example |
|---------|-------------|---------|
| **Latency** | No round-trip to cloud | Voice assistant responds in 50ms vs 500ms |
| **Privacy** | Data never leaves device | Health data stays on phone |
| **Offline** | Works without internet | AI in airplane mode, rural areas |
| **Cost at scale** | No per-inference API costs | 1B users × 100 queries/day = $$$$ if cloud |
| **Bandwidth** | Don't send raw video/audio | Security camera processes locally |

**When cloud is still better:**
- Need the largest models (GPT-4 class)
- Need to process data from multiple devices together
- Device is too constrained (cheap IoT sensors)
- Model updates need to be immediate

---

## Model Compression Techniques

### 1. Quantization (Reduce Number Precision)

Like rounding numbers: instead of storing 3.14159265, store 3.14 or even just 3.

```
FP32 (32-bit float):  3.14159265358979...  → 4 bytes per parameter
FP16 (16-bit float):  3.14159...           → 2 bytes per parameter
INT8 (8-bit integer): 3                    → 1 byte per parameter
INT4 (4-bit integer): [0-15 range]         → 0.5 bytes per parameter
```

**Impact on a 7B parameter model:**

| Precision | Model Size | RAM Needed | Quality Loss |
|-----------|-----------|------------|--------------|
| FP32 | 28 GB | ~32 GB | None (baseline) |
| FP16 | 14 GB | ~16 GB | Negligible |
| INT8 | 7 GB | ~8 GB | Small (~1-2%) |
| INT4 | 3.5 GB | ~4 GB | Moderate (~3-5%) |

**Quantization types:**
- **Post-training quantization (PTQ):** Quantize after training. Simple, some quality loss.
- **Quantization-aware training (QAT):** Train with quantization in mind. Better quality, more effort.

### 2. Pruning (Remove Unnecessary Connections)

Like trimming a tree — remove branches that don't bear fruit.

```
Before pruning: All neurons connected (dense)
After pruning: 50-90% of connections removed (sparse)
Result: Faster inference, smaller model, minimal quality loss
```

**Types:**
- **Unstructured pruning:** Remove individual weights (flexible but hardware-unfriendly)
- **Structured pruning:** Remove entire neurons/layers (hardware-friendly)

### 3. Knowledge Distillation

Train a small "student" model to mimic a large "teacher" model.

```mermaid
flowchart TD
    A[Large Teacher Model 70B] --> B[Generate outputs on training data]
    B --> C[Training pairs: input → teacher output]
    C --> D[Train Small Student Model 7B]
    D --> E[Student mimics teacher behavior]
    
    style A fill:#e8eaf6
    style E fill:#e8f5e9
```

### 4. Neural Architecture Search (NAS)

Automatically find the most efficient model architecture for a given constraint (e.g., "must run in 50ms on iPhone").

---

## Deployment Formats

| Format | Platform | Optimized For |
|--------|----------|--------------|
| **ONNX** | Cross-platform | Portability, CPU/GPU |
| **TensorRT** | NVIDIA GPUs | Maximum GPU throughput |
| **Core ML** | Apple (iOS/macOS) | Apple Neural Engine |
| **TensorFlow Lite** | Android/iOS/embedded | Mobile, microcontrollers |
| **WASM** | Browser | Web deployment, any OS |
| **GGUF** | CPU (llama.cpp) | LLMs on consumer hardware |

### Conversion Pipeline

```mermaid
flowchart LR
    A[PyTorch Model] --> B{Target?}
    B -->|Apple| C[CoreML via coremltools]
    B -->|NVIDIA| D[TensorRT via torch2trt]
    B -->|Mobile| E[TFLite via ai_edge_torch]
    B -->|Cross-platform| F[ONNX via torch.onnx]
    B -->|Browser| G[ONNX → WASM]
    B -->|CPU LLM| H[GGUF via llama.cpp]
```

---

## Hybrid Cloud-Edge Architectures

The best systems use BOTH edge and cloud intelligently:

```mermaid
flowchart TD
    A[User Input] --> B{Complexity?}
    
    B -->|Simple| C[Edge Model on Device]
    B -->|Complex| D[Cloud Model API]
    
    C --> E{Confident?}
    E -->|Yes| F[Return Edge Result]
    E -->|No| D
    
    D --> G[Return Cloud Result]
    
    style C fill:#e8f5e9
    style D fill:#e3f2fd
    style F fill:#c8e6c9
```

### Pattern 1: Complexity-Based Routing

```
Simple queries (autocomplete, classification) → Edge (fast, free)
Complex queries (multi-step reasoning, generation) → Cloud (capable, costly)
```

### Pattern 2: Privacy-Based Routing

```
Sensitive data (health, finance, personal) → Edge (private)
Non-sensitive data (general questions) → Cloud (better quality)
```

### Pattern 3: Sync Between Edge and Cloud

```mermaid
flowchart LR
    subgraph Edge Device
        A[Local Model]
        B[Local Cache]
        C[Offline Queue]
    end
    
    subgraph Cloud
        D[Full Model]
        E[Model Registry]
        F[Training Pipeline]
    end
    
    A -->|Periodic sync| E
    C -->|When online| D
    F -->|Model updates| A
    
    style A fill:#e8f5e9
    style D fill:#e3f2fd
```

---

## Edge Inference Frameworks

| Framework | Focus | Models |
|-----------|-------|--------|
| **Ollama** | Easy local LLMs | Llama, Mistral, Phi |
| **llama.cpp** | CPU-optimized LLMs | Any GGUF model |
| **ExecuTorch** | Mobile/edge PyTorch | Any PyTorch model |
| **MLX** | Apple Silicon optimized | LLMs, diffusion |
| **MLC LLM** | Universal LLM deployment | Multiple platforms |
| **ONNX Runtime** | Cross-platform inference | Any ONNX model |

---

## Hardware for Edge AI

| Hardware | Found In | AI Performance |
|----------|----------|----------------|
| **Apple Neural Engine** | iPhone, Mac | 15-35 TOPS |
| **Qualcomm Hexagon NPU** | Android phones | 10-45 TOPS |
| **NVIDIA Jetson** | Robots, drones | 100-275 TOPS |
| **Intel NPU** | Laptops | 10-40 TOPS |
| **Google Tensor (TPU)** | Pixel phones | ~10 TOPS |
| **CPU only** | Anything | 1-5 TOPS |

*TOPS = Trillion Operations Per Second*

---

## Real-World Edge AI Examples

### Smartphone Keyboard Prediction
- Model: Tiny transformer (~5MB)
- Latency: < 10ms
- Privacy: Keystrokes never leave device
- Approach: Federated learning (train across devices without sharing data)

### Smart Home Voice Assistant
- Wake word detection: Edge (always listening, tiny model)
- Full speech recognition: Cloud (more capable)
- Response: Cloud (LLM reasoning)
- TTS: Edge or cloud depending on quality needs

### Autonomous Vehicles
- Object detection: Edge (can't wait for cloud, lives at stake)
- Route planning: Hybrid (real-time local + cloud for traffic)
- Model updates: Downloaded overnight via WiFi

---

## Practical Considerations

### Memory Budget on Devices

```
iPhone 15 Pro: 8 GB total RAM, ~4 GB available for AI
  → Can run: 4-bit quantized 7B model (3.5 GB)
  → Cannot run: Anything larger without swapping

MacBook M3 Pro: 18-36 GB unified memory
  → Can run: 4-bit quantized 70B model (~35 GB on 36GB model)
  
Raspberry Pi 5: 8 GB RAM
  → Can run: Small models (< 3B parameters quantized)
```

### Battery Impact

AI inference drains battery. Design for:
- Batch processing when charging
- Lightweight models for continuous tasks
- NPU (more efficient) over GPU over CPU

---

## Key Takeaways

1. **Edge AI** trades model capability for latency, privacy, and cost savings
2. **Quantization** (INT4/INT8) is the most impactful compression technique
3. **Hybrid architectures** route simple/sensitive tasks to edge, complex tasks to cloud
4. **GGUF + llama.cpp** is the current standard for running LLMs on consumer hardware
5. **NPUs** are 10-100x more power-efficient than CPUs for AI workloads
6. **The trend is clear:** Models are getting smaller and more capable — edge AI will only grow

---

## Next Steps

- Build the [Edge Inference Program](./programs/edge-inference/) to benchmark quantization effects
- Consider hybrid architectures that combine edge with [Streaming Pipelines](./01-streaming-and-real-time-ai.md)

---

## Anti-Patterns

### 1. Trying to Run Full-Size Models on Edge

**What goes wrong:** Team deploys unquantized 7B+ model to mobile device. App crashes on low-memory devices, inference takes 30+ seconds, device overheats, battery drains in minutes.

**Rule:** Always quantize for edge. There is no scenario where full-precision models belong on consumer devices.

**Decision ladder:**
- Phone (4-8GB RAM): INT4 quantized models ≤ 3B params
- Laptop (16-32GB RAM): INT4 quantized models ≤ 13B params
- Edge server (64GB+ RAM): INT8 quantized models ≤ 70B params

### 2. No Model Update Strategy for Deployed Devices

**What goes wrong:** Model ships with app v1.0. Bugs are found, quality degrades, world changes. But model is baked into the binary. Users stuck on bad model until next app store update (which they may never install).

**Fix:**
- Separate model from application binary (download on first launch)
- Background model updates (like app updates but for weights only)
- Version negotiation: device reports model version, server recommends update
- Rollback capability: keep previous model version on device
- A/B testing: serve different model versions to different device cohorts

### 3. Ignoring Battery/Thermal Constraints

**What goes wrong:** Continuous AI inference heats device to thermal throttling. OS kills your app or reduces CPU/GPU frequency. User experience degrades progressively. Battery life drops from 8 hours to 2 hours.

**Fix:**
- Monitor thermal state and reduce inference frequency when hot
- Batch inference requests (one larger call vs many small calls)
- Use NPU when available (10-100x more power efficient than CPU)
- Defer non-urgent inference to when device is charging
- Set inference budgets: max N inferences per minute

### 4. Edge-Only Without Cloud Fallback

**What goes wrong:** Edge model can't handle complex queries. User gets bad answers with no recourse. No way to improve — edge model is static and limited.

**Fix:**
- Confidence-based routing: if edge model confidence < threshold, route to cloud
- Graceful messaging: "For this complex question, let me check with a more capable model..."
- Offline queue: if cloud is unavailable, queue complex queries for later
- Hybrid UX: instant edge response + cloud "enhancement" that arrives seconds later

---

## Key Trade-offs

### Edge (Private, Fast, Limited) vs Cloud (Powerful, Latency, Privacy Risk)

| Factor | Edge | Cloud |
|--------|------|-------|
| Latency | 10-100ms | 200-2000ms |
| Privacy | Data stays on device | Data leaves device |
| Model capability | Small models only (≤13B) | Full-size models (GPT-4 class) |
| Cost at scale | Zero marginal cost per inference | $0.01-0.10 per request |
| Offline support | Full functionality | None |
| Model updates | Slow (app update cycle) | Instant (server-side) |
| Consistency | Device-dependent behavior | Same for all users |

**Decision framework:**
- Latency-critical (< 100ms) → Edge
- Privacy-sensitive (health, finance, personal) → Edge
- Complex reasoning needed → Cloud
- Offline requirement → Edge with cloud enhancement
- Consistency requirement → Cloud (same model for all users)

### Model Size vs Capability (The Edge Frontier)

```
Model size → Capability mapping (2024):
  1-3B params:  Simple classification, extraction, short generation
  7B params:    Decent general assistant, good at specific tasks when fine-tuned
  13B params:   Strong general capability, approaching GPT-3.5 level
  70B params:   Near GPT-4 level on many tasks (but needs edge server)
  
What fits where (INT4 quantized):
  Smartphone:     ≤ 3B  (fast, good for narrow tasks)
  Laptop:         ≤ 13B (good general assistant)  
  Edge server:    ≤ 70B (near cloud quality)
```

**Key insight:** A fine-tuned 3B model on a specific task often beats a general 13B model. For edge, specialization > size.

### When Edge AI is Worth the Complexity

**Worth it:**
- 1B+ users (cloud costs would be $millions/month)
- Regulated industries (data cannot leave device/premises)
- Real-time requirements (autonomous vehicles, AR)
- Offline-first products (field workers, rural areas)

**Not worth it:**
- Internal tools with < 1000 users (cloud is simpler and cheap enough)
- Tasks requiring frontier model intelligence
- Rapid iteration phase (cloud lets you update instantly)
- When model quality directly impacts revenue (use the best model available)
