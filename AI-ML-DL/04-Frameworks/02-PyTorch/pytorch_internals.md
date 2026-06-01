# PyTorch Internals Deep Dive

## Table of Contents
- [How Autograd Really Works](#how-autograd-really-works)
- [Memory Management](#memory-management)
- [Tensor Storage Internals](#tensor-storage-internals)
- [JIT Compilation and torch.compile](#jit-compilation-and-torchcompile)

---

## How Autograd Really Works

### The Computational Graph (Dynamic DAG)

PyTorch builds a **Directed Acyclic Graph (DAG)** of operations dynamically during the forward pass. Unlike TensorFlow 1.x (static graph), PyTorch rebuilds the graph every iteration — this is why it's called "define-by-run."

```
Forward Pass builds the graph:

    x (leaf)     w (leaf, requires_grad=True)
       \           /
        \         /
         MatMul          b (leaf, requires_grad=True)
            \           /
             \         /
              Add
               |
             ReLU
               |
             output
```

Each node in the graph is a `grad_fn` — a reference to the `Function` that created the tensor. Leaf tensors (created by the user, not by an operation) have `grad_fn = None`.

```python
import torch

x = torch.randn(3, 3, requires_grad=True)  # leaf tensor
y = x * 2                                    # y.grad_fn = <MulBackward0>
z = y.mean()                                 # z.grad_fn = <MeanBackward0>

# The graph: x -> Mul -> y -> Mean -> z
print(z.grad_fn)                             # <MeanBackward0 object>
print(z.grad_fn.next_functions)              # links back to MulBackward0
print(z.grad_fn.next_functions[0][0].next_functions)  # links back to AccumulateGrad (x)
```

### Tape-Based Automatic Differentiation

PyTorch uses **reverse-mode automatic differentiation** (backpropagation). Conceptually:

1. **Forward pass**: Execute operations, recording each op onto a "tape" (the DAG)
2. **Backward pass**: Walk the tape in reverse, applying the chain rule

This is NOT symbolic differentiation (like Mathematica) or numerical differentiation (finite differences). It's algorithmic/automatic differentiation that computes exact gradients efficiently.

```
Mathematical Chain Rule:
    dz/dx = dz/dy * dy/dx

Autograd applies this recursively through the graph:
    
    z = mean(y)      →  dz/dy = 1/n (for each element)
    y = x * 2        →  dy/dx = 2
    
    Therefore: dz/dx = (1/n) * 2
```

### Backward Pass Implementation

When you call `loss.backward()`:

1. Start from the output tensor (loss)
2. The `grad_fn` of loss computes local gradients
3. Propagate to each input's `grad_fn` via `next_functions`
4. Continue until reaching leaf tensors
5. Accumulate gradients in leaf tensor's `.grad` attribute

```python
import torch

# Detailed example showing backward mechanics
a = torch.tensor([2.0, 3.0], requires_grad=True)
b = torch.tensor([6.0, 4.0], requires_grad=True)

Q = 3*a**3 - b**2

# Compute gradients
# dQ/da = 9a^2, dQ/db = -2b
external_grad = torch.tensor([1.0, 1.0])  # gradient of subsequent operations
Q.backward(gradient=external_grad)

print(a.grad)  # tensor([36., 81.])  = 9 * [4, 9]
print(b.grad)  # tensor([-12., -8.]) = -2 * [6, 4]
```

### `requires_grad`, `grad_fn`, `retain_graph`

#### `requires_grad`
- Signals to autograd that this tensor needs gradient computation
- Only float and complex tensors can require gradients
- Default: `False` for user-created tensors, `True` for `nn.Parameter`

```python
# Inference optimization - no graph is built
x = torch.randn(1000, 1000, requires_grad=False)
y = x @ x  # No graph overhead, faster

# Training - graph is built
x = torch.randn(1000, 1000, requires_grad=True)
y = x @ x  # Records operation in graph
```

#### `grad_fn`
- Every tensor created by an operation has a `grad_fn`
- It stores the backward function for that operation
- Leaf tensors have `grad_fn = None`

```python
x = torch.randn(3, requires_grad=True)
print(x.grad_fn)      # None (leaf tensor)
print(x.is_leaf)      # True

y = x ** 2
print(y.grad_fn)      # <PowBackward0>
print(y.is_leaf)      # False
```

#### `retain_graph`
- By default, the computational graph is freed after `.backward()` to save memory
- Use `retain_graph=True` when you need to backward through the graph multiple times

```python
x = torch.randn(3, requires_grad=True)
y = x ** 2
z = y.sum()

# First backward - graph still exists
z.backward(retain_graph=True)
print(x.grad)  # tensor([...])

# Second backward - would fail without retain_graph=True
x.grad.zero_()  # Must zero gradients first!
z.backward()    # Works because we retained
print(x.grad)   # Same values as before
```

**When is `retain_graph` needed?**
- Multiple backward passes (e.g., GANs with separate generator/discriminator losses)
- Computing higher-order derivatives
- Debugging gradient flow

### Custom Autograd Functions

When built-in operations aren't sufficient, create custom autograd functions:

```python
import torch
from torch.autograd import Function

class CustomReLU(Function):
    """
    Custom ReLU implementation showing the autograd.Function pattern.
    
    Key rules:
    1. forward() takes ctx + inputs, returns output
    2. backward() takes ctx + grad_output, returns grad_input (one per forward input)
    3. Use ctx.save_for_backward() to save tensors needed in backward
    4. Must be STATIC methods decorated with @staticmethod
    """
    
    @staticmethod
    def forward(ctx, input):
        # ctx is a context object for stashing information for backward
        ctx.save_for_backward(input)
        return input.clamp(min=0)
    
    @staticmethod
    def backward(ctx, grad_output):
        # grad_output is dL/d(output)
        # We need to return dL/d(input) = dL/d(output) * d(output)/d(input)
        input, = ctx.saved_tensors
        grad_input = grad_output.clone()
        grad_input[input < 0] = 0  # d(ReLU)/dx = 0 for x < 0, 1 for x > 0
        return grad_input

# Usage
custom_relu = CustomReLU.apply
x = torch.randn(5, requires_grad=True)
y = custom_relu(x)
y.sum().backward()
print(x.grad)  # Gradient is 1 where x > 0, 0 where x < 0
```

**Advanced custom function — Straight-Through Estimator:**

```python
class StraightThroughEstimator(Function):
    """Used for quantization-aware training where forward is non-differentiable."""
    
    @staticmethod
    def forward(ctx, input):
        # Quantize to {-1, +1}
        return torch.sign(input)
    
    @staticmethod
    def backward(ctx, grad_output):
        # Straight-through: pretend the function is identity in backward
        return grad_output  # Pass gradient through unchanged
```

### Gradient Accumulation and `zero_grad()` Necessity

**Critical concept**: PyTorch ACCUMULATES gradients by default. It does NOT replace them.

```python
x = torch.tensor([1.0, 2.0, 3.0], requires_grad=True)

# First backward
y = (x * 2).sum()
y.backward()
print(x.grad)  # tensor([2., 2., 2.])

# Second backward WITHOUT zeroing
y = (x * 3).sum()
y.backward()
print(x.grad)  # tensor([5., 5., 5.])  ← ACCUMULATED! (2 + 3)

# This is why we need zero_grad():
x.grad.zero_()
y = (x * 3).sum()
y.backward()
print(x.grad)  # tensor([3., 3., 3.])  ← Correct
```

**Why does PyTorch accumulate by design?**
1. RNNs: shared parameters across time steps naturally need accumulation
2. Gradient accumulation for large effective batch sizes
3. Multiple losses contributing to the same parameters

**The standard training pattern:**

```python
optimizer.zero_grad()       # Reset gradients to zero
output = model(input)       # Forward pass (builds graph)
loss = criterion(output, target)
loss.backward()             # Backward pass (computes gradients)
optimizer.step()            # Update parameters using gradients
```

---

## Memory Management

### GPU Memory Allocation and Caching Allocator

PyTorch uses a **caching memory allocator** for CUDA tensors. Instead of calling `cudaMalloc`/`cudaFree` for every tensor (which are expensive synchronization points), it:

1. Allocates large blocks from CUDA
2. Subdivides them for individual tensors
3. When tensors are freed, memory returns to the cache (not to CUDA)
4. Reuses cached memory for future allocations

```
┌─────────────────────────────────────────────────┐
│              GPU Physical Memory                 │
├─────────────────────────────────────────────────┤
│  PyTorch Caching Allocator                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │ Block 1  │ │ Block 2  │ │   Block 3    │   │
│  │ [used]   │ │ [cached] │ │   [used]     │   │
│  │ tensor_a │ │ (free)   │ │  tensor_b    │   │
│  └──────────┘ └──────────┘ └──────────────┘   │
│                                                 │
│  nvidia-smi shows Block 1+2+3 as "used"        │
│  torch.cuda.memory_allocated() shows 1+3 only  │
└─────────────────────────────────────────────────┘
```

```python
import torch

# Memory tracking
print(torch.cuda.memory_allocated())   # Actively used memory
print(torch.cuda.memory_reserved())    # Total memory held by allocator (cached)
print(torch.cuda.max_memory_allocated())  # Peak usage

# Force release cached memory back to CUDA (rarely needed)
torch.cuda.empty_cache()

# Memory snapshot for debugging
torch.cuda.memory._record_memory_history()
# ... run your code ...
torch.cuda.memory._dump_snapshot("memory_snapshot.pickle")
```

### Memory Pinning (`pin_memory`)

**Page-locked (pinned) memory** enables faster CPU→GPU transfers:

```
Without pinning:
    CPU pageable memory → CPU pinned buffer → GPU memory
    (requires extra copy)

With pinning:
    CPU pinned memory → GPU memory (direct DMA transfer)
    (faster, but pinned memory is limited)
```

```python
# In DataLoader - most common usage
train_loader = DataLoader(
    dataset, 
    batch_size=32, 
    pin_memory=True,  # Allocates batches in pinned memory
    num_workers=4
)

# Manual pinning
tensor = torch.randn(1000, 1000).pin_memory()
# Non-blocking transfer (overlap compute and data transfer)
gpu_tensor = tensor.to('cuda', non_blocking=True)
```

**When to use `pin_memory`:**
- Always when using GPU training with DataLoader
- When doing manual CPU→GPU transfers that can be overlapped
- NOT when you're memory-constrained on CPU (pinned memory can't be swapped)

### Gradient Checkpointing (Trading Compute for Memory)

Normal backprop stores ALL intermediate activations. For deep networks, this is enormous:

```
Normal:     Save everything    →  Memory: O(n) where n = number of layers
Checkpoint: Recompute on the fly → Memory: O(√n), but ~33% slower
```

```python
from torch.utils.checkpoint import checkpoint, checkpoint_sequential

class DeepModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.layers = nn.ModuleList([Block() for _ in range(100)])
    
    def forward(self, x):
        for layer in self.layers:
            # Instead of: x = layer(x)  [stores activation]
            x = checkpoint(layer, x, use_reentrant=False)  # Recomputes in backward
        return x

# Or for sequential models:
model = nn.Sequential(*[Block() for _ in range(100)])
# checkpoint_sequential splits into segments
output = checkpoint_sequential(model, segments=10, input=x)
```

### `torch.no_grad()` vs `torch.inference_mode()`

Both disable gradient computation, but they differ:

| Feature | `torch.no_grad()` | `torch.inference_mode()` |
|---------|-------------------|--------------------------|
| Disables grad tracking | Yes | Yes |
| Tensors can be used in autograd later | Yes | No |
| Memory savings | Moderate | Maximum |
| Speed | Fast | Fastest |
| Use case | Validation during training | Pure inference/deployment |

```python
# torch.no_grad() - safe for validation during training
model.eval()
with torch.no_grad():
    val_output = model(val_input)
    # val_output CAN still be used in autograd if needed later
    # But no graph is built for operations inside this block

# torch.inference_mode() - maximum performance for inference
model.eval()
with torch.inference_mode():
    output = model(input)
    # output CANNOT be used in any autograd computation
    # Attempting to do so raises an error
    # But this is faster and uses less memory
```

### Memory Profiling

```python
import torch
from torch.profiler import profile, ProfilerActivity

# PyTorch Profiler
with profile(
    activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA],
    profile_memory=True,
    record_shapes=True
) as prof:
    model(input)

print(prof.key_averages().table(sort_by="cuda_memory_usage", row_limit=10))

# Simple memory tracking context manager
class MemoryTracker:
    def __enter__(self):
        torch.cuda.reset_peak_memory_stats()
        self.start = torch.cuda.memory_allocated()
        return self
    
    def __exit__(self, *args):
        self.end = torch.cuda.memory_allocated()
        self.peak = torch.cuda.max_memory_allocated()
        print(f"Allocated: {(self.end - self.start) / 1e6:.1f} MB")
        print(f"Peak: {self.peak / 1e6:.1f} MB")
```

---

## Tensor Storage Internals

### Storage vs Tensor (View Semantics)

A Tensor is a **view** into a contiguous block of memory called `Storage`:

```
Storage: [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]  ← actual memory

Tensor A (2x3 view):        Tensor B (3x2 view):
┌─────────────┐              ┌─────────┐
│ 1.0 2.0 3.0│              │ 1.0 2.0 │
│ 4.0 5.0 6.0│              │ 3.0 4.0 │
└─────────────┘              │ 5.0 6.0 │
                             └─────────┘
Both share the SAME Storage!
```

```python
import torch

x = torch.arange(6, dtype=torch.float32)
print(x.storage())  # [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]

# Multiple views of the same storage
a = x.view(2, 3)
b = x.view(3, 2)

# Modifying one affects the other!
a[0, 0] = 999
print(b[0, 0])  # tensor(999.) - same underlying memory

# Check if tensors share storage
print(a.data_ptr() == b.data_ptr())  # True
print(a.storage().data_ptr() == b.storage().data_ptr())  # True
```

**Key operations that create views (shared memory):**
- `view()`, `reshape()` (when possible), `transpose()`, `permute()`
- `narrow()`, `expand()`, slicing (`x[::2]`)
- `unsqueeze()`, `squeeze()`

**Operations that create copies (new memory):**
- `clone()`, `contiguous()` (when needed), `reshape()` (sometimes)

### Contiguous vs Non-Contiguous

A tensor is **contiguous** if its elements are laid out in memory in the order you'd expect from its shape (row-major / C-order):

```python
x = torch.arange(12).view(3, 4)
print(x.is_contiguous())  # True
# Memory: [0,1,2,3,4,5,6,7,8,9,10,11]
# Access [i,j] = memory[i*4 + j]  ← strides match layout

y = x.t()  # Transpose
print(y.is_contiguous())  # False!
# y's logical shape is (4, 3)
# But memory is still: [0,1,2,3,4,5,6,7,8,9,10,11]
# Access y[i,j] = memory[i*1 + j*4]  ← non-standard strides

# Many operations require contiguous tensors:
z = y.contiguous()  # Creates a new copy in contiguous layout
# Now memory is: [0,4,8,1,5,9,2,6,10,3,7,11]
```

### Stride-Based Indexing

Strides define how to jump through memory to reach the next element along each dimension:

```
Tensor shape: (3, 4)
Strides: (4, 1)  ← "jump 4 to go to next row, jump 1 to go to next column"

Memory offset for element [i, j] = i * stride[0] + j * stride[1]
Element [2, 3] = 2*4 + 3*1 = 11th position in storage
```

```python
x = torch.arange(12).view(3, 4)
print(x.stride())  # (4, 1)

# Transpose changes strides, not memory!
y = x.t()
print(y.shape)     # torch.Size([4, 3])
print(y.stride())  # (1, 4)  ← swapped!

# Slicing with step changes strides
z = x[::2, ::2]   # Every other row and column
print(z.shape)     # torch.Size([2, 2])
print(z.stride())  # (8, 2)

# expand() uses stride trick (zero stride = broadcast)
a = torch.tensor([1, 2, 3])  # shape (3,), stride (1,)
b = a.unsqueeze(0).expand(4, 3)  # shape (4, 3), stride (0, 1)
# stride 0 means "don't advance in memory" → same row repeated
print(b.stride())  # (0, 1)
```

---

## JIT Compilation and torch.compile

### TorchScript (`torch.jit.script`, `torch.jit.trace`)

TorchScript converts Python PyTorch code into a serializable, optimizable intermediate representation:

#### `torch.jit.trace` — Records operations on example input

```python
import torch
import torch.nn as nn

class SimpleModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.linear = nn.Linear(10, 5)
    
    def forward(self, x):
        return self.linear(x).relu()

model = SimpleModel()
example_input = torch.randn(1, 10)

# Trace records the operations for this specific input
traced_model = torch.jit.trace(model, example_input)
traced_model.save("model.pt")

# Load without Python
loaded = torch.jit.load("model.pt")
output = loaded(torch.randn(1, 10))
```

**Limitation of tracing**: Control flow (if/else, loops) is NOT captured. Only the path taken with the example input is recorded.

#### `torch.jit.script` — Parses Python code into TorchScript

```python
@torch.jit.script
def compute(x: torch.Tensor, threshold: float = 0.5) -> torch.Tensor:
    if x.mean() > threshold:  # Control flow IS captured
        return x * 2
    else:
        return x * 0.5

# Works with modules too
class ScriptableModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.linear = nn.Linear(10, 5)
    
    @torch.jit.export
    def predict(self, x: torch.Tensor) -> torch.Tensor:
        return self.forward(x)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.linear(x)
        if out.mean() > 0:
            return out.relu()
        return out

scripted = torch.jit.script(ScriptableModel())
```

### `torch.compile` (PyTorch 2.0+)

The modern compilation approach. Much simpler and more powerful than TorchScript:

```
┌─────────────────────────────────────────────────┐
│               torch.compile Pipeline             │
├─────────────────────────────────────────────────┤
│                                                  │
│  Python Code                                     │
│       │                                          │
│       ▼                                          │
│  TorchDynamo (graph capture via bytecode)        │
│       │                                          │
│       ▼                                          │
│  AOTAutograd (ahead-of-time backward graph)      │
│       │                                          │
│       ▼                                          │
│  TorchInductor (generates Triton/C++ kernels)    │
│       │                                          │
│       ▼                                          │
│  Optimized executable code                       │
│                                                  │
└─────────────────────────────────────────────────┘
```

```python
import torch

model = MyModel().cuda()

# Simple usage - just wrap the model
compiled_model = torch.compile(model)

# With options
compiled_model = torch.compile(
    model,
    mode="reduce-overhead",  # Options: "default", "reduce-overhead", "max-autotune"
    fullgraph=True,          # Ensure entire model is one graph (errors on graph breaks)
    dynamic=True,            # Handle dynamic shapes without recompilation
)

# Can also compile individual functions
@torch.compile
def custom_loss(pred, target):
    return ((pred - target) ** 2).mean() + 0.1 * pred.abs().mean()
```

**Compilation modes:**
- `"default"`: Balanced speed/compile-time
- `"reduce-overhead"`: Minimizes Python overhead (uses CUDA graphs)
- `"max-autotune"`: Tries many kernel variants, slowest compile but fastest runtime

### When to Use Which Compilation Strategy

| Scenario | Recommendation |
|----------|---------------|
| Research/prototyping | No compilation (eager mode) |
| Training speedup (PyTorch 2.0+) | `torch.compile` |
| Deployment to non-Python env | TorchScript or ONNX export |
| Production serving (Python) | `torch.compile` with `reduce-overhead` |
| Mobile deployment | TorchScript → TorchMobile |
| Dynamic control flow + deployment | `torch.jit.script` |
| Fixed model + deployment | `torch.jit.trace` or ONNX |

**Key insight**: `torch.compile` is for **speedup**, TorchScript is for **portability**. They solve different problems.

---

## Summary of Key Internals

```
PyTorch Execution Model:
═══════════════════════

Eager Mode (default):
  Python → ATen ops (C++) → CUDA kernels → Results
  + Dynamic graph built as side effect

Compiled Mode (torch.compile):
  Python → Dynamo captures graph → Inductor optimizes → Fused kernels → Results
  + Up to 2x speedup for free

TorchScript Mode:
  Python → IR (intermediate representation) → Optimized IR → Execution
  + Portable, no Python dependency

Memory Model:
═══════════════
  Tensor ←→ Storage (shared via views)
  Strides define logical layout over physical memory
  Caching allocator pools GPU memory
  Autograd graph holds references (memory leak risk if not careful)
```
