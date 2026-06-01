# TensorFlow Internals: Deep Dive

## Table of Contents
- [TensorFlow Architecture](#tensorflow-architecture)
- [Computation Graph](#computation-graph)
- [Memory Management](#memory-management)
- [tf.data Pipeline Internals](#tfdata-pipeline-internals)

---

## TensorFlow Architecture

### Eager Execution vs Graph Execution

TensorFlow 2.x defaults to eager execution, where operations execute immediately and return concrete values. This contrasts with TensorFlow 1.x's graph execution model.

```python
import tensorflow as tf

# Eager execution (default in TF2)
a = tf.constant([[1, 2], [3, 4]])
b = tf.constant([[5, 6], [7, 8]])
c = tf.matmul(a, b)
print(c.numpy())  # Immediately available - no session needed

# Graph execution (explicit via tf.function)
@tf.function
def matmul_graph(x, y):
    return tf.matmul(x, y)

result = matmul_graph(a, b)  # Traced, compiled, then executed
```

**Key Differences:**

| Aspect | Eager | Graph |
|--------|-------|-------|
| Debugging | Easy (pdb, print work) | Hard (print becomes tf.print) |
| Performance | Slower (Python overhead) | Faster (optimized, fused ops) |
| Control flow | Native Python | AutoGraph conversion |
| Deployment | Not serializable | SavedModel compatible |
| Memory | Less optimized | Better memory planning |

**When to Use Each:**
- **Eager**: Development, debugging, prototyping, dynamic models
- **Graph**: Production, serving, performance-critical paths, TPU execution

---

### tf.function and Tracing

`tf.function` is the bridge between eager and graph execution. It converts Python functions into TensorFlow graphs through a process called **tracing**.

```python
@tf.function
def compute(x):
    print("Tracing!")  # Only prints during tracing, NOT during execution
    tf.print("Executing!")  # Prints during every execution
    return x * x + 2 * x + 1

# First call: traces the function (creates graph)
result1 = compute(tf.constant(3.0))   # Prints "Tracing!" and "Executing!"

# Second call with same type/shape: reuses graph
result2 = compute(tf.constant(5.0))   # Only prints "Executing!"

# Different type triggers retrace
result3 = compute(tf.constant(3))     # Prints "Tracing!" and "Executing!" (int vs float)
```

**Tracing Mechanism:**

```
┌─────────────────────────────────────────────────────────┐
│                    tf.function Call                       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. Inspect input signatures (dtype, shape, value)      │
│  2. Check cache for matching ConcreteFunction           │
│  3. If miss → Trace:                                    │
│     a. Replace inputs with symbolic tensors             │
│     b. Execute Python code (builds graph nodes)         │
│     c. Capture graph as ConcreteFunction                │
│     d. Cache with input signature                       │
│  4. Execute ConcreteFunction with actual values         │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Retracing Pitfalls:**

```python
# BAD: Python values cause retracing for every unique value
@tf.function
def bad_function(x, n):  # n is a Python int
    return x ** n

for i in range(100):
    bad_function(tf.constant(2.0), i)  # 100 retraces!

# GOOD: Use tensors for values that change
@tf.function
def good_function(x, n):
    return x ** n

for i in range(100):
    good_function(tf.constant(2.0), tf.constant(i))  # 1 trace (same signature)

# GOOD: Use input_signature to fix the signature
@tf.function(input_signature=[tf.TensorSpec(shape=[], dtype=tf.float32)])
def fixed_function(x):
    return x * x
```

---

### AutoGraph: Automatic Control Flow Conversion

AutoGraph transforms Python control flow (if/else, for, while) into TensorFlow graph operations (`tf.cond`, `tf.while_loop`).

```python
@tf.function
def autograph_example(x):
    # Python if → tf.cond (when condition depends on tensor)
    if x > 0:
        result = x * 2
    else:
        result = x * -1
    
    # Python for with tensor range → tf.while_loop
    total = tf.constant(0.0)
    for i in tf.range(x):
        total += tf.cast(i, tf.float32)
    
    return result, total

# See the generated code
print(tf.autograph.to_code(autograph_example.python_function))
```

**AutoGraph Rules:**
1. `if tensor_condition` → `tf.cond`
2. `for i in tf.range(n)` → `tf.while_loop`
3. `while tensor_condition` → `tf.while_loop`
4. Python-value conditions are traced only once (compile-time constant)

**Common AutoGraph Pitfalls:**

```python
@tf.function
def pitfall_example(x):
    # PITFALL 1: Appending to Python list inside tf loop
    results = []  # This won't work as expected in graph mode
    for i in tf.range(5):
        results.append(i)  # Creates graph nodes, not a Python list
    
    # CORRECT: Use TensorArray
    results = tf.TensorArray(dtype=tf.int32, size=5)
    for i in tf.range(5):
        results = results.write(i, i * x)
    return results.stack()

@tf.function
def pitfall_variables(x):
    # PITFALL 2: Creating variables inside tf.function
    # v = tf.Variable(0.0)  # ERROR! Variables must be created outside
    pass

# Variables must be created outside tf.function
v = tf.Variable(0.0)

@tf.function
def correct_variable_use(x):
    v.assign(x)  # OK: assigning to existing variable
    return v
```

---

### XLA Compilation (Accelerated Linear Algebra)

XLA is TensorFlow's optimizing compiler that fuses operations and generates efficient machine code.

```python
# Enable XLA for a function
@tf.function(jit_compile=True)
def xla_compiled(x, y):
    # XLA will fuse these operations into one kernel
    z = x + y
    return z * z

# Enable XLA globally for all tf.functions
tf.config.optimizer.set_jit(True)

# XLA with mixed precision
policy = tf.keras.mixed_precision.Policy('mixed_float16')
tf.keras.mixed_precision.set_global_policy(policy)

@tf.function(jit_compile=True)
def xla_mixed_precision(x, y):
    return tf.matmul(x, y)  # Uses float16 compute, float32 accumulation
```

**XLA Optimization Passes:**
```
┌──────────────────────────────────────────────────┐
│              XLA Compilation Pipeline              │
├──────────────────────────────────────────────────┤
│                                                  │
│  TF Graph → HLO IR → Optimizations → Machine Code│
│                                                  │
│  Optimizations:                                  │
│  ├── Operation fusion (reduce kernel launches)   │
│  ├── Memory planning (reduce allocations)        │
│  ├── Layout optimization (NCHW vs NHWC)         │
│  ├── Algebraic simplification                    │
│  ├── Dead code elimination                       │
│  └── Constant folding                           │
│                                                  │
└──────────────────────────────────────────────────┘
```

**When XLA Helps Most:**
- Many small element-wise operations (fused into one kernel)
- TPU execution (XLA is required for TPU)
- Models with predictable shapes (XLA needs static shapes)

**When XLA Hurts:**
- Dynamic shapes (causes recompilation)
- Sparse operations
- Custom ops without XLA support

---

### tf.Variable vs tf.constant

```python
# tf.constant: immutable tensor, value embedded in graph
c = tf.constant([1.0, 2.0, 3.0])
# - Stored in graph definition
# - Copied to every device that uses it
# - Cannot be modified after creation
# - Good for hyperparameters, fixed data

# tf.Variable: mutable tensor, managed by resource manager
v = tf.Variable([1.0, 2.0, 3.0])
# - Stored outside graph (resource handle in graph)
# - Persists across tf.function calls
# - Can be modified via assign, assign_add, assign_sub
# - Used for model weights, optimizer state
# - Has a device placement
# - Supports aggregation (for distribution strategies)

v.assign([4.0, 5.0, 6.0])       # Overwrite
v.assign_add([1.0, 1.0, 1.0])   # In-place add
v.assign_sub([0.5, 0.5, 0.5])   # In-place subtract

# Variables track gradients by default
with tf.GradientTape() as tape:
    y = v * v  # v is automatically watched
grad = tape.gradient(y, v)  # dy/dv = 2v
```

---

## Computation Graph

### Static vs Dynamic Graphs (TF1 vs TF2)

```
TF1 (Static Graph - Define and Run):
┌─────────────┐    ┌──────────┐    ┌──────────────┐
│ Define Graph │ →  │ Compile  │ →  │ Run in       │
│ (Python)     │    │ & Optimize│   │ Session      │
└─────────────┘    └──────────┘    └──────────────┘

TF2 (Dynamic by default, Static via tf.function):
┌─────────────────────────────────────────────────┐
│ Eager: Ops execute immediately (like NumPy)      │
│ tf.function: Traces → Graph → Optimize → Execute│
└─────────────────────────────────────────────────┘
```

### Graph Optimization Passes

When `tf.function` creates a graph, TensorFlow applies optimization passes:

```python
# View optimized graph
@tf.function
def example(x):
    y = x + 0       # Algebraic identity - will be removed
    z = y * 1       # Algebraic identity - will be removed
    unused = x * 2  # Dead code - will be removed
    return z + 1

# Get concrete function and inspect
cf = example.get_concrete_function(tf.TensorSpec(shape=[], dtype=tf.float32))
print(cf.graph.as_graph_def())
```

**Optimization Passes Applied:**
1. **Constant Folding**: Evaluate operations with constant inputs at compile time
2. **Common Subexpression Elimination**: Reuse identical computations
3. **Dead Code Elimination**: Remove unused operations
4. **Operation Fusion**: Merge compatible operations
5. **Layout Optimization**: Choose optimal data format (NCHW/NHWC)
6. **Memory Optimization**: Plan memory reuse across operations
7. **Arithmetic Optimization**: Simplify algebraic expressions

### How tf.function Traces and Retraces

```python
@tf.function
def polymorphic(x):
    return x + 1

# Each unique input signature creates a new trace
polymorphic(tf.constant(1.0))      # Trace 1: float32 scalar
polymorphic(tf.constant([1.0]))    # Trace 2: float32 vector
polymorphic(tf.constant(1))        # Trace 3: int32 scalar

# Check number of cached traces
print(len(polymorphic._list_all_concrete_functions()))  # 3
```

**Retrace Triggers:**
- Different tensor dtype
- Different tensor rank (ndim)
- Different tensor shape (unless using None dimensions)
- Different Python value (int, float, string arguments)
- Different Python object identity (for non-hashable)

### Concrete Functions

```python
# Get a concrete function for a specific signature
@tf.function
def my_func(x, y):
    return x + y

# Create concrete function (fixed signature, no more retracing)
concrete = my_func.get_concrete_function(
    tf.TensorSpec(shape=[None, 10], dtype=tf.float32),
    tf.TensorSpec(shape=[None, 10], dtype=tf.float32)
)

# Concrete functions are what get saved in SavedModel
print(concrete.structured_input_signature)
print(concrete.output_shapes)

# Call directly (no tracing overhead)
result = concrete(tf.ones([5, 10]), tf.ones([5, 10]))
```

---

## Memory Management

### GPU Memory Growth Configuration

```python
# Option 1: Allow memory growth (allocate as needed)
gpus = tf.config.list_physical_devices('GPU')
for gpu in gpus:
    tf.config.experimental.set_memory_growth(gpu, True)

# Option 2: Set hard memory limit
tf.config.set_logical_device_configuration(
    gpus[0],
    [tf.config.LogicalDeviceConfiguration(memory_limit=4096)]  # 4GB
)

# Option 3: Environment variable (before importing TF)
# TF_FORCE_GPU_ALLOW_GROWTH=true

# Check current memory usage
print(tf.config.experimental.get_memory_info('GPU:0'))
# {'current': 1234567, 'peak': 2345678}
```

### Memory Profiling with TensorBoard

```python
# Profile memory usage
tf.profiler.experimental.start('logdir')

# Run your training step
model.fit(dataset, epochs=1, steps_per_epoch=10)

tf.profiler.experimental.stop()

# Programmatic profiling
with tf.profiler.experimental.Profile('logdir'):
    model.fit(dataset, epochs=1, steps_per_epoch=10)

# Launch TensorBoard
# tensorboard --logdir=logdir
```

### Mixed Precision with tf.keras.mixed_precision

```python
# Set global policy
tf.keras.mixed_precision.set_global_policy('mixed_float16')

# Model automatically uses float16 for compute, float32 for variables
model = tf.keras.Sequential([
    tf.keras.layers.Dense(512, activation='relu'),   # float16 compute
    tf.keras.layers.Dense(512, activation='relu'),   # float16 compute
    tf.keras.layers.Dense(10),                        # float16 compute
])

# Loss scale optimizer prevents underflow in float16 gradients
optimizer = tf.keras.optimizers.Adam(1e-3)
# In TF2.11+, loss scaling is automatic with mixed precision

# Custom training with mixed precision
@tf.function
def train_step(x, y):
    with tf.GradientTape() as tape:
        predictions = model(x, training=True)
        loss = loss_fn(y, predictions)
        # Scale loss if using LossScaleOptimizer
        scaled_loss = optimizer.get_scaled_loss(loss) if hasattr(optimizer, 'get_scaled_loss') else loss
    
    scaled_gradients = tape.gradient(scaled_loss, model.trainable_variables)
    gradients = optimizer.get_unscaled_gradients(scaled_gradients) if hasattr(optimizer, 'get_unscaled_gradients') else scaled_gradients
    optimizer.apply_gradients(zip(gradients, model.trainable_variables))
    return loss
```

**Memory savings with mixed precision:**
```
┌─────────────────────────────────────────────────┐
│         Mixed Precision Memory Impact            │
├─────────────────────────────────────────────────┤
│ Component       │ float32  │ mixed_float16      │
│ Weights         │ 4 bytes  │ 4 bytes (master)   │
│ Activations     │ 4 bytes  │ 2 bytes (-50%)     │
│ Gradients       │ 4 bytes  │ 2 bytes (-50%)     │
│ Optimizer state │ 4 bytes  │ 4 bytes            │
│                                                  │
│ Net effect: ~40% memory reduction on large models│
│ Speed: 2-3x on Tensor Cores (V100, A100, H100) │
└─────────────────────────────────────────────────┘
```

### Gradient Tape Internals

```python
# GradientTape records operations for automatic differentiation
x = tf.Variable(3.0)
y = tf.Variable(4.0)

with tf.GradientTape(persistent=True) as tape:
    # Tape records: z = x^2 + x*y
    z = x**2 + x * y

# Compute gradients
dz_dx = tape.gradient(z, x)  # 2x + y = 10
dz_dy = tape.gradient(z, y)  # x = 3
del tape  # Release resources (persistent tape)

# Higher-order gradients
x = tf.Variable(2.0)
with tf.GradientTape() as outer_tape:
    with tf.GradientTape() as inner_tape:
        y = x ** 3
    dy_dx = inner_tape.gradient(y, x)     # 3x^2 = 12
d2y_dx2 = outer_tape.gradient(dy_dx, x)   # 6x = 12

# Watch non-Variable tensors
x = tf.constant(3.0)
with tf.GradientTape() as tape:
    tape.watch(x)  # Explicitly watch constants
    y = x ** 2
dy_dx = tape.gradient(y, x)  # 6.0
```

**How GradientTape Works Internally:**
```
┌────────────────────────────────────────────────────┐
│              GradientTape Mechanism                  │
├────────────────────────────────────────────────────┤
│                                                    │
│  Forward Pass (recorded on tape):                  │
│  ┌─────┐    ┌──────┐    ┌──────┐    ┌─────┐     │
│  │  x  │ →  │ op1  │ →  │ op2  │ →  │  y  │     │
│  └─────┘    └──────┘    └──────┘    └─────┘     │
│                                                    │
│  Backward Pass (tape replayed in reverse):         │
│  ┌─────┐    ┌──────┐    ┌──────┐    ┌─────┐     │
│  │dy/dx│ ←  │∂op1/∂│ ←  │∂op2/∂│ ←  │dy/dy│    │
│  └─────┘    └──────┘    └──────┘    └─────┘     │
│                                                    │
│  - Each op has a registered gradient function      │
│  - Tape stores op type + inputs (not activations) │
│  - Non-persistent tape releases after gradient()  │
│  - Persistent tape allows multiple gradient()     │
│                                                    │
└────────────────────────────────────────────────────┘
```

---

## tf.data Pipeline Internals

### Performance Model

```python
import tensorflow as tf

# Naive pipeline (sequential, slow)
dataset_slow = tf.data.Dataset.from_tensor_slices(filenames)
dataset_slow = dataset_slow.map(parse_fn)     # Sequential map

# Optimized pipeline
dataset_fast = tf.data.Dataset.from_tensor_slices(filenames)
dataset_fast = dataset_fast.interleave(
    lambda x: tf.data.TFRecordDataset(x),
    cycle_length=4,                # Read 4 files concurrently
    num_parallel_calls=tf.data.AUTOTUNE,
    deterministic=False            # Allow out-of-order for speed
)
dataset_fast = dataset_fast.map(
    parse_fn,
    num_parallel_calls=tf.data.AUTOTUNE  # Parallel map
)
dataset_fast = dataset_fast.cache()      # Cache after expensive ops
dataset_fast = dataset_fast.shuffle(buffer_size=10000)
dataset_fast = dataset_fast.batch(32)
dataset_fast = dataset_fast.prefetch(tf.data.AUTOTUNE)  # Overlap with training
```

**Pipeline Execution Model:**
```
Without Prefetch:
┌───────┐  ┌───────┐  ┌───────┐  ┌───────┐  ┌───────┐
│ Load  │  │ Train │  │ Load  │  │ Train │  │ Load  │ ...
└───────┘  └───────┘  └───────┘  └───────┘  └───────┘
          Time ──────────────────────────────────────→

With Prefetch:
┌───────┐  ┌───────┐  ┌───────┐  ┌───────┐
│ Load  │  │ Load  │  │ Load  │  │ Load  │  ...
├───────┤  ├───────┤  ├───────┤  ├───────┤
│       │  │ Train │  │ Train │  │ Train │  ...
└───────┘  └───────┘  └───────┘  └───────┘
          Time ─────────────────────────→  (faster!)

With Parallel Map + Prefetch:
┌────┐┌────┐  ┌────┐┌────┐  ┌────┐┌────┐
│Map1││Map2│  │Map1││Map2│  │Map1││Map2│  ...
├────┤├────┤  ├────┤├────┤  ├────┤├────┤
│         │  │ Train    │  │ Train    │  ...
└─────────┘  └─────────┘  └─────────┘
```

### Input Pipeline Bottleneck Analysis

```python
# Enable pipeline profiling
tf.data.experimental.enable_debug_mode()

# Use TensorBoard profiler for input pipeline analysis
options = tf.data.Options()
options.experimental_optimization.map_parallelization = True
options.experimental_optimization.parallel_batch = True
dataset = dataset.with_options(options)

# Benchmark pipeline throughput
import time

def benchmark(dataset, num_epochs=2):
    start_time = time.perf_counter()
    for epoch in range(num_epochs):
        for batch in dataset:
            # Simulate training step
            time.sleep(0.01)
    duration = time.perf_counter() - start_time
    print(f"{num_epochs} epochs: {duration:.2f}s")

# Compare different configurations
benchmark(dataset_slow)   # Baseline
benchmark(dataset_fast)   # Optimized
```

### tf.data Service (Distributed Data Loading)

```python
# tf.data service offloads preprocessing to dedicated workers
# Useful when input pipeline is the bottleneck

# Start a dispatcher
# tf.data.experimental.service.DispatchServer(port=5000)

# Start workers
# tf.data.experimental.service.WorkerServer(port=5001, dispatcher_address="localhost:5000")

# Client-side: distribute dataset processing
dataset = dataset.apply(
    tf.data.experimental.service.distribute(
        processing_mode="distributed_epoch",
        service="grpc://localhost:5000"
    )
)
```

### TFRecord Format and Optimization

```python
# Writing TFRecords
def serialize_example(image, label):
    feature = {
        'image': tf.train.Feature(bytes_list=tf.train.BytesList(value=[image.numpy()])),
        'label': tf.train.Feature(int64_list=tf.train.Int64List(value=[label.numpy()])),
    }
    proto = tf.train.Example(features=tf.train.Features(feature=feature))
    return proto.SerializeToString()

# Write with sharding for parallel reads
num_shards = 16
writers = [tf.io.TFRecordWriter(f'data-{i:05d}.tfrecord') for i in range(num_shards)]
for i, (image, label) in enumerate(dataset):
    writers[i % num_shards].write(serialize_example(image, label))
for w in writers:
    w.close()

# Reading TFRecords optimally
def parse_tfrecord(serialized):
    features = tf.io.parse_single_example(serialized, {
        'image': tf.io.FixedLenFeature([], tf.string),
        'label': tf.io.FixedLenFeature([], tf.int64),
    })
    image = tf.io.decode_raw(features['image'], tf.float32)
    return image, features['label']

# Optimal reading pattern
files = tf.data.Dataset.list_files('data-*.tfrecord', shuffle=True)
dataset = files.interleave(
    tf.data.TFRecordDataset,
    cycle_length=8,
    num_parallel_calls=tf.data.AUTOTUNE
)
dataset = dataset.map(parse_tfrecord, num_parallel_calls=tf.data.AUTOTUNE)
dataset = dataset.batch(64).prefetch(tf.data.AUTOTUNE)
```

---

## Performance Profiling Examples

### End-to-End Profiling

```python
# Profile a training step
log_dir = "logs/profile"
tf.profiler.experimental.start(log_dir)

for step, (x, y) in enumerate(dataset):
    if step == 50:
        break
    with tf.profiler.experimental.Trace('train', step_num=step):
        train_step(x, y)

tf.profiler.experimental.stop()

# Callback-based profiling
tensorboard_callback = tf.keras.callbacks.TensorBoard(
    log_dir=log_dir,
    profile_batch='10,20'  # Profile batches 10-20
)
model.fit(dataset, epochs=5, callbacks=[tensorboard_callback])
```

### Identifying Bottlenecks

```python
# Time each operation
import time

class TimingCallback(tf.keras.callbacks.Callback):
    def __init__(self):
        self.times = []
    
    def on_train_batch_begin(self, batch, logs=None):
        self.batch_start = time.perf_counter()
    
    def on_train_batch_end(self, batch, logs=None):
        self.times.append(time.perf_counter() - self.batch_start)
    
    def on_epoch_end(self, epoch, logs=None):
        avg = sum(self.times) / len(self.times)
        print(f"Avg batch time: {avg*1000:.1f}ms")
        self.times = []

# Device placement logging
tf.debugging.set_log_device_placement(True)  # See where ops run
```

---

## Summary: TensorFlow Execution Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    TensorFlow Runtime Stack                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Python API (tf.keras, tf.data, tf.function)                    │
│  ─────────────────────────────────────────────                  │
│  Eager Runtime │ Graph Runtime (tf.function)                     │
│  ─────────────────────────────────────────────                  │
│  Graph Optimization (Grappler)                                  │
│  ─────────────────────────────────────────────                  │
│  XLA Compiler (optional) │ TF Runtime                           │
│  ─────────────────────────────────────────────                  │
│  Device Layer (CPU, GPU/CUDA, TPU)                              │
│  ─────────────────────────────────────────────                  │
│  Hardware (x86, ARM, NVIDIA GPU, Google TPU)                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```
