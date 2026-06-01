# TensorFlow Advanced Patterns

## Table of Contents
- [Custom Training Loops](#custom-training-loops)
- [Custom Layers and Models](#custom-layers-and-models)
- [Advanced Architectures](#advanced-architectures)
- [Distribution Strategies](#distribution-strategies)
- [TensorFlow Serving](#tensorflow-serving-production-deployment)
- [TFX Pipeline](#tfx-tensorflow-extended-pipeline)
- [TensorFlow Lite](#tensorflow-lite)

---

## Custom Training Loops

### tf.GradientTape for Custom Training

```python
import tensorflow as tf

model = tf.keras.Sequential([
    tf.keras.layers.Dense(128, activation='relu'),
    tf.keras.layers.Dropout(0.2),
    tf.keras.layers.Dense(10)
])

optimizer = tf.keras.optimizers.Adam(learning_rate=1e-3)
loss_fn = tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True)

# Metrics
train_loss = tf.keras.metrics.Mean(name='train_loss')
train_accuracy = tf.keras.metrics.SparseCategoricalAccuracy(name='train_accuracy')

@tf.function
def train_step(images, labels):
    with tf.GradientTape() as tape:
        predictions = model(images, training=True)
        loss = loss_fn(labels, predictions)
        # Add regularization losses
        loss += sum(model.losses)
    
    gradients = tape.gradient(loss, model.trainable_variables)
    
    # Optional: gradient clipping
    gradients, _ = tf.clip_by_global_norm(gradients, max_norm=1.0)
    
    optimizer.apply_gradients(zip(gradients, model.trainable_variables))
    
    train_loss.update_state(loss)
    train_accuracy.update_state(labels, predictions)
    return loss

# Training loop
EPOCHS = 10
for epoch in range(EPOCHS):
    train_loss.reset_states()
    train_accuracy.reset_states()
    
    for images, labels in train_dataset:
        loss = train_step(images, labels)
    
    print(f'Epoch {epoch+1}, '
          f'Loss: {train_loss.result():.4f}, '
          f'Accuracy: {train_accuracy.result():.4f}')
```

### Multiple Losses and Multi-Task Learning

```python
class MultiTaskModel(tf.keras.Model):
    def __init__(self):
        super().__init__()
        self.shared_backbone = tf.keras.Sequential([
            tf.keras.layers.Dense(256, activation='relu'),
            tf.keras.layers.Dense(128, activation='relu'),
        ])
        self.classification_head = tf.keras.layers.Dense(10, activation='softmax')
        self.regression_head = tf.keras.layers.Dense(1)
    
    def call(self, inputs, training=False):
        shared = self.shared_backbone(inputs, training=training)
        cls_output = self.classification_head(shared)
        reg_output = self.regression_head(shared)
        return cls_output, reg_output

model = MultiTaskModel()
cls_loss_fn = tf.keras.losses.SparseCategoricalCrossentropy()
reg_loss_fn = tf.keras.losses.MeanSquaredError()

@tf.function
def multi_task_train_step(x, cls_labels, reg_labels):
    with tf.GradientTape() as tape:
        cls_pred, reg_pred = model(x, training=True)
        cls_loss = cls_loss_fn(cls_labels, cls_pred)
        reg_loss = reg_loss_fn(reg_labels, reg_pred)
        # Weighted combination
        total_loss = 0.7 * cls_loss + 0.3 * reg_loss
    
    gradients = tape.gradient(total_loss, model.trainable_variables)
    optimizer.apply_gradients(zip(gradients, model.trainable_variables))
    return cls_loss, reg_loss, total_loss
```

### Custom Metrics

```python
class F1Score(tf.keras.metrics.Metric):
    def __init__(self, num_classes, average='macro', name='f1_score', **kwargs):
        super().__init__(name=name, **kwargs)
        self.num_classes = num_classes
        self.average = average
        self.true_positives = self.add_weight(name='tp', shape=(num_classes,), initializer='zeros')
        self.false_positives = self.add_weight(name='fp', shape=(num_classes,), initializer='zeros')
        self.false_negatives = self.add_weight(name='fn', shape=(num_classes,), initializer='zeros')
    
    def update_state(self, y_true, y_pred, sample_weight=None):
        y_pred = tf.argmax(y_pred, axis=-1)
        y_true = tf.cast(y_true, tf.int64)
        y_pred = tf.cast(y_pred, tf.int64)
        
        for i in range(self.num_classes):
            true_mask = tf.equal(y_true, i)
            pred_mask = tf.equal(y_pred, i)
            
            tp = tf.reduce_sum(tf.cast(true_mask & pred_mask, tf.float32))
            fp = tf.reduce_sum(tf.cast(~true_mask & pred_mask, tf.float32))
            fn = tf.reduce_sum(tf.cast(true_mask & ~pred_mask, tf.float32))
            
            self.true_positives[i].assign_add(tp)
            self.false_positives[i].assign_add(fp)
            self.false_negatives[i].assign_add(fn)
    
    def result(self):
        precision = self.true_positives / (self.true_positives + self.false_positives + 1e-7)
        recall = self.true_positives / (self.true_positives + self.false_negatives + 1e-7)
        f1 = 2 * precision * recall / (precision + recall + 1e-7)
        
        if self.average == 'macro':
            return tf.reduce_mean(f1)
        return f1
    
    def reset_state(self):
        self.true_positives.assign(tf.zeros_like(self.true_positives))
        self.false_positives.assign(tf.zeros_like(self.false_positives))
        self.false_negatives.assign(tf.zeros_like(self.false_negatives))
```

### Custom Callbacks

```python
class CosineAnnealingCallback(tf.keras.callbacks.Callback):
    """Cosine annealing learning rate with warm restarts."""
    
    def __init__(self, initial_lr, T_max, T_mult=2, eta_min=1e-6):
        super().__init__()
        self.initial_lr = initial_lr
        self.T_max = T_max
        self.T_mult = T_mult
        self.eta_min = eta_min
        self.current_epoch = 0
        self.cycle_epoch = 0
        self.current_T = T_max
    
    def on_epoch_begin(self, epoch, logs=None):
        import math
        lr = self.eta_min + (self.initial_lr - self.eta_min) * \
             (1 + math.cos(math.pi * self.cycle_epoch / self.current_T)) / 2
        self.model.optimizer.learning_rate.assign(lr)
        
        self.cycle_epoch += 1
        if self.cycle_epoch >= self.current_T:
            self.cycle_epoch = 0
            self.current_T = int(self.current_T * self.T_mult)


class GradientMonitorCallback(tf.keras.callbacks.Callback):
    """Monitor gradient norms during training."""
    
    def __init__(self, log_dir):
        super().__init__()
        self.writer = tf.summary.create_file_writer(log_dir)
    
    def on_train_batch_end(self, batch, logs=None):
        if batch % 100 == 0:
            with self.writer.as_default():
                for var in self.model.trainable_variables:
                    tf.summary.histogram(f'weights/{var.name}', var, step=batch)


class EarlyStoppingWithRestore(tf.keras.callbacks.Callback):
    """Early stopping that restores best weights."""
    
    def __init__(self, patience=5, monitor='val_loss', min_delta=1e-4):
        super().__init__()
        self.patience = patience
        self.monitor = monitor
        self.min_delta = min_delta
        self.best_weights = None
        self.best_value = float('inf')
        self.wait = 0
    
    def on_epoch_end(self, epoch, logs=None):
        current = logs.get(self.monitor)
        if current < self.best_value - self.min_delta:
            self.best_value = current
            self.best_weights = self.model.get_weights()
            self.wait = 0
        else:
            self.wait += 1
            if self.wait >= self.patience:
                self.model.set_weights(self.best_weights)
                self.model.stop_training = True
                print(f"\nRestored best weights from epoch {epoch - self.wait}")
```

---

## Custom Layers and Models

### Subclassing tf.keras.layers.Layer

```python
class MultiHeadSelfAttention(tf.keras.layers.Layer):
    def __init__(self, embed_dim, num_heads, **kwargs):
        super().__init__(**kwargs)
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        assert embed_dim % num_heads == 0, "embed_dim must be divisible by num_heads"
    
    def build(self, input_shape):
        # Lazy initialization - called once when first input shape is known
        self.query = self.add_weight(
            name='query', shape=(self.embed_dim, self.embed_dim),
            initializer='glorot_uniform', trainable=True
        )
        self.key = self.add_weight(
            name='key', shape=(self.embed_dim, self.embed_dim),
            initializer='glorot_uniform', trainable=True
        )
        self.value = self.add_weight(
            name='value', shape=(self.embed_dim, self.embed_dim),
            initializer='glorot_uniform', trainable=True
        )
        self.output_projection = self.add_weight(
            name='output', shape=(self.embed_dim, self.embed_dim),
            initializer='glorot_uniform', trainable=True
        )
        super().build(input_shape)
    
    def call(self, inputs, mask=None, training=False):
        batch_size = tf.shape(inputs)[0]
        seq_len = tf.shape(inputs)[1]
        
        Q = tf.matmul(inputs, self.query)
        K = tf.matmul(inputs, self.key)
        V = tf.matmul(inputs, self.value)
        
        # Reshape for multi-head
        Q = tf.reshape(Q, (batch_size, seq_len, self.num_heads, self.head_dim))
        Q = tf.transpose(Q, perm=[0, 2, 1, 3])  # (batch, heads, seq, head_dim)
        K = tf.reshape(K, (batch_size, seq_len, self.num_heads, self.head_dim))
        K = tf.transpose(K, perm=[0, 2, 1, 3])
        V = tf.reshape(V, (batch_size, seq_len, self.num_heads, self.head_dim))
        V = tf.transpose(V, perm=[0, 2, 1, 3])
        
        # Scaled dot-product attention
        scale = tf.math.sqrt(tf.cast(self.head_dim, tf.float32))
        attention_scores = tf.matmul(Q, K, transpose_b=True) / scale
        
        if mask is not None:
            attention_scores += (mask * -1e9)
        
        attention_weights = tf.nn.softmax(attention_scores, axis=-1)
        output = tf.matmul(attention_weights, V)
        
        # Concat heads
        output = tf.transpose(output, perm=[0, 2, 1, 3])
        output = tf.reshape(output, (batch_size, seq_len, self.embed_dim))
        
        return tf.matmul(output, self.output_projection)
    
    def get_config(self):
        config = super().get_config()
        config.update({
            'embed_dim': self.embed_dim,
            'num_heads': self.num_heads,
        })
        return config
```

### Subclassing tf.keras.Model

```python
class TransformerBlock(tf.keras.layers.Layer):
    def __init__(self, embed_dim, num_heads, ff_dim, dropout_rate=0.1, **kwargs):
        super().__init__(**kwargs)
        self.attention = MultiHeadSelfAttention(embed_dim, num_heads)
        self.ffn = tf.keras.Sequential([
            tf.keras.layers.Dense(ff_dim, activation='gelu'),
            tf.keras.layers.Dense(embed_dim),
        ])
        self.layernorm1 = tf.keras.layers.LayerNormalization(epsilon=1e-6)
        self.layernorm2 = tf.keras.layers.LayerNormalization(epsilon=1e-6)
        self.dropout1 = tf.keras.layers.Dropout(dropout_rate)
        self.dropout2 = tf.keras.layers.Dropout(dropout_rate)
    
    def call(self, inputs, training=False):
        # Pre-norm architecture
        x = self.layernorm1(inputs)
        attn_output = self.attention(x, training=training)
        attn_output = self.dropout1(attn_output, training=training)
        x = inputs + attn_output
        
        ffn_input = self.layernorm2(x)
        ffn_output = self.ffn(ffn_input)
        ffn_output = self.dropout2(ffn_output, training=training)
        return x + ffn_output


class VisionTransformer(tf.keras.Model):
    def __init__(self, image_size, patch_size, num_classes, embed_dim,
                 num_heads, num_layers, ff_dim, dropout_rate=0.1):
        super().__init__()
        self.patch_size = patch_size
        num_patches = (image_size // patch_size) ** 2
        
        self.patch_embed = tf.keras.layers.Dense(embed_dim)
        self.pos_embed = self.add_weight(
            'pos_embed', shape=(1, num_patches + 1, embed_dim),
            initializer='random_normal'
        )
        self.cls_token = self.add_weight(
            'cls_token', shape=(1, 1, embed_dim),
            initializer='random_normal'
        )
        
        self.transformer_blocks = [
            TransformerBlock(embed_dim, num_heads, ff_dim, dropout_rate)
            for _ in range(num_layers)
        ]
        
        self.norm = tf.keras.layers.LayerNormalization(epsilon=1e-6)
        self.classifier = tf.keras.layers.Dense(num_classes)
    
    def extract_patches(self, images):
        batch_size = tf.shape(images)[0]
        patches = tf.image.extract_patches(
            images,
            sizes=[1, self.patch_size, self.patch_size, 1],
            strides=[1, self.patch_size, self.patch_size, 1],
            rates=[1, 1, 1, 1],
            padding='VALID'
        )
        patch_dim = patches.shape[-1]
        patches = tf.reshape(patches, [batch_size, -1, patch_dim])
        return patches
    
    def call(self, inputs, training=False):
        batch_size = tf.shape(inputs)[0]
        patches = self.extract_patches(inputs)
        x = self.patch_embed(patches)
        
        cls_tokens = tf.broadcast_to(self.cls_token, [batch_size, 1, x.shape[-1]])
        x = tf.concat([cls_tokens, x], axis=1)
        x = x + self.pos_embed
        
        for block in self.transformer_blocks:
            x = block(x, training=training)
        
        x = self.norm(x)
        cls_output = x[:, 0]
        return self.classifier(cls_output)
```

### Custom build() Method (Lazy Initialization)

```python
class FlexibleDense(tf.keras.layers.Layer):
    """Dense layer that infers input dimension at first call."""
    
    def __init__(self, units, **kwargs):
        super().__init__(**kwargs)
        self.units = units
    
    def build(self, input_shape):
        # Called automatically the first time the layer is used
        # input_shape gives us the shape of the input tensor
        self.w = self.add_weight(
            shape=(input_shape[-1], self.units),
            initializer='glorot_uniform',
            trainable=True,
            name='kernel'
        )
        self.b = self.add_weight(
            shape=(self.units,),
            initializer='zeros',
            trainable=True,
            name='bias'
        )
    
    def call(self, inputs):
        return tf.matmul(inputs, self.w) + self.b
    
    def get_config(self):
        config = super().get_config()
        config.update({'units': self.units})
        return config
    
    @classmethod
    def from_config(cls, config):
        return cls(**config)
```

---

## Advanced Architectures

### Multi-Input, Multi-Output Models (Functional API)

```python
# Text + Image → Classification + Confidence
text_input = tf.keras.Input(shape=(100,), name='text_input')
image_input = tf.keras.Input(shape=(224, 224, 3), name='image_input')

# Text branch
text_features = tf.keras.layers.Embedding(10000, 64)(text_input)
text_features = tf.keras.layers.LSTM(128)(text_features)

# Image branch
image_features = tf.keras.applications.ResNet50(
    include_top=False, weights='imagenet', pooling='avg'
)(image_input)

# Fusion
merged = tf.keras.layers.Concatenate()([text_features, image_features])
merged = tf.keras.layers.Dense(256, activation='relu')(merged)
merged = tf.keras.layers.Dropout(0.3)(merged)

# Multiple outputs
classification = tf.keras.layers.Dense(10, activation='softmax', name='class')(merged)
confidence = tf.keras.layers.Dense(1, activation='sigmoid', name='confidence')(merged)

model = tf.keras.Model(
    inputs=[text_input, image_input],
    outputs=[classification, confidence]
)

model.compile(
    optimizer='adam',
    loss={'class': 'sparse_categorical_crossentropy', 'confidence': 'binary_crossentropy'},
    loss_weights={'class': 1.0, 'confidence': 0.5},
    metrics={'class': 'accuracy', 'confidence': 'mae'}
)
```

### Shared Layers and Siamese Networks

```python
def create_siamese_network(input_shape, embedding_dim=128):
    # Shared encoder
    encoder = tf.keras.Sequential([
        tf.keras.layers.Conv2D(32, 3, activation='relu'),
        tf.keras.layers.MaxPooling2D(),
        tf.keras.layers.Conv2D(64, 3, activation='relu'),
        tf.keras.layers.MaxPooling2D(),
        tf.keras.layers.Flatten(),
        tf.keras.layers.Dense(embedding_dim),
        tf.keras.layers.Lambda(lambda x: tf.math.l2_normalize(x, axis=1))
    ], name='shared_encoder')
    
    input_a = tf.keras.Input(shape=input_shape, name='anchor')
    input_b = tf.keras.Input(shape=input_shape, name='comparison')
    
    # Same encoder, shared weights
    embedding_a = encoder(input_a)
    embedding_b = encoder(input_b)
    
    # Contrastive distance
    distance = tf.keras.layers.Lambda(
        lambda x: tf.reduce_sum(tf.square(x[0] - x[1]), axis=1, keepdims=True)
    )([embedding_a, embedding_b])
    
    model = tf.keras.Model(inputs=[input_a, input_b], outputs=distance)
    return model

# Contrastive loss
def contrastive_loss(y_true, y_pred, margin=1.0):
    """y_true=1 means same class, y_true=0 means different class."""
    square_pred = tf.square(y_pred)
    margin_square = tf.square(tf.maximum(margin - y_pred, 0))
    return tf.reduce_mean(y_true * square_pred + (1 - y_true) * margin_square)
```

### Custom Training with train_step Override

```python
class GANModel(tf.keras.Model):
    def __init__(self, generator, discriminator, latent_dim):
        super().__init__()
        self.generator = generator
        self.discriminator = discriminator
        self.latent_dim = latent_dim
    
    def compile(self, g_optimizer, d_optimizer, loss_fn):
        super().compile()
        self.g_optimizer = g_optimizer
        self.d_optimizer = d_optimizer
        self.loss_fn = loss_fn
        self.g_loss_metric = tf.keras.metrics.Mean(name='g_loss')
        self.d_loss_metric = tf.keras.metrics.Mean(name='d_loss')
    
    @property
    def metrics(self):
        return [self.g_loss_metric, self.d_loss_metric]
    
    def train_step(self, real_images):
        batch_size = tf.shape(real_images)[0]
        noise = tf.random.normal(shape=(batch_size, self.latent_dim))
        
        # Train discriminator
        with tf.GradientTape() as tape:
            fake_images = self.generator(noise, training=True)
            real_output = self.discriminator(real_images, training=True)
            fake_output = self.discriminator(fake_images, training=True)
            
            real_loss = self.loss_fn(tf.ones_like(real_output), real_output)
            fake_loss = self.loss_fn(tf.zeros_like(fake_output), fake_output)
            d_loss = (real_loss + fake_loss) / 2
        
        d_grads = tape.gradient(d_loss, self.discriminator.trainable_variables)
        self.d_optimizer.apply_gradients(
            zip(d_grads, self.discriminator.trainable_variables))
        
        # Train generator
        noise = tf.random.normal(shape=(batch_size, self.latent_dim))
        with tf.GradientTape() as tape:
            fake_images = self.generator(noise, training=True)
            fake_output = self.discriminator(fake_images, training=True)
            g_loss = self.loss_fn(tf.ones_like(fake_output), fake_output)
        
        g_grads = tape.gradient(g_loss, self.generator.trainable_variables)
        self.g_optimizer.apply_gradients(
            zip(g_grads, self.generator.trainable_variables))
        
        self.g_loss_metric.update_state(g_loss)
        self.d_loss_metric.update_state(d_loss)
        return {'g_loss': self.g_loss_metric.result(), 'd_loss': self.d_loss_metric.result()}
```

---

## Distribution Strategies

### Strategy Overview

```
┌─────────────────────────────────────────────────────────────┐
│              TensorFlow Distribution Strategies               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  MirroredStrategy        │ 1 machine, N GPUs               │
│  MultiWorkerMirrored     │ N machines, M GPUs each         │
│  TPUStrategy             │ Google Cloud TPU pods            │
│  ParameterServerStrategy │ Large-scale async training       │
│  CentralStorageStrategy  │ 1 machine, CPU+GPU (small model)│
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### MirroredStrategy (Single Machine, Multi-GPU)

```python
strategy = tf.distribute.MirroredStrategy()
# Uses all available GPUs, NCCL for all-reduce

print(f'Number of devices: {strategy.num_replicas_in_sync}')

with strategy.scope():
    model = tf.keras.Sequential([
        tf.keras.layers.Dense(128, activation='relu'),
        tf.keras.layers.Dense(10)
    ])
    model.compile(
        optimizer='adam',
        loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
        metrics=['accuracy']
    )

# Batch size scales with number of GPUs
BATCH_SIZE_PER_REPLICA = 64
GLOBAL_BATCH_SIZE = BATCH_SIZE_PER_REPLICA * strategy.num_replicas_in_sync

dataset = dataset.batch(GLOBAL_BATCH_SIZE)
model.fit(dataset, epochs=10)
```

### MultiWorkerMirroredStrategy

```python
# Set TF_CONFIG environment variable on each worker
import json, os

tf_config = {
    'cluster': {
        'worker': ['worker0:port', 'worker1:port', 'worker2:port']
    },
    'task': {'type': 'worker', 'index': 0}  # Different on each worker
}
os.environ['TF_CONFIG'] = json.dumps(tf_config)

strategy = tf.distribute.MultiWorkerMirroredStrategy()

with strategy.scope():
    model = create_model()
    model.compile(optimizer='adam', loss='sparse_categorical_crossentropy')

# Each worker processes a shard of the data
model.fit(dataset, epochs=10)
```

### TPUStrategy

```python
# Connect to TPU
resolver = tf.distribute.cluster_resolver.TPUClusterResolver(tpu='my-tpu')
tf.config.experimental_connect_to_cluster(resolver)
tf.tpu.experimental.initialize_tpu_system(resolver)

strategy = tf.distribute.TPUStrategy(resolver)

with strategy.scope():
    model = create_model()
    model.compile(optimizer='adam', loss='sparse_categorical_crossentropy')

model.fit(dataset, epochs=10)
```

### ParameterServerStrategy

```python
# For very large models that don't fit on one machine
cluster_resolver = tf.distribute.cluster_resolver.TFConfigClusterResolver()
strategy = tf.distribute.ParameterServerStrategy(cluster_resolver)

# Coordinator creates the model
with strategy.scope():
    model = create_large_model()
    model.compile(optimizer='adam', loss='sparse_categorical_crossentropy')

# Use ParameterServerStrategy's custom training loop
coordinator = tf.distribute.experimental.coordinator.ClusterCoordinator(strategy)

@tf.function
def per_worker_dataset_fn():
    return create_dataset().batch(64)

distributed_dataset = coordinator.create_per_worker_dataset(per_worker_dataset_fn)
```

### How to Choose Strategy

| Scenario | Strategy | Notes |
|----------|----------|-------|
| 1 machine, 2-8 GPUs | MirroredStrategy | Simplest, fastest for small clusters |
| Multiple machines, data parallelism | MultiWorkerMirrored | Synchronous, good for most cases |
| Google Cloud TPU | TPUStrategy | Required for TPU |
| Very large model, async | ParameterServer | Model doesn't fit on one GPU |
| Research/small model | Default (no strategy) | No distribution overhead |

---

## TensorFlow Serving (Production Deployment)

### SavedModel Format in Detail

```python
# Save model
model.save('my_model')

# SavedModel directory structure:
# my_model/
# ├── saved_model.pb          # Graph definition + metadata
# ├── fingerprint.pb          # Model fingerprint
# ├── variables/
# │   ├── variables.index     # Variable index
# │   └── variables.data-00000-of-00001  # Variable values
# └── assets/                 # Extra files (vocab, etc.)

# Save with custom signatures
@tf.function(input_signature=[tf.TensorSpec(shape=[None, 784], dtype=tf.float32)])
def serving_fn(x):
    return {'predictions': model(x, training=False)}

tf.saved_model.save(model, 'my_model', signatures={'serving_default': serving_fn})

# Inspect SavedModel
# saved_model_cli show --dir my_model --all

# Load and use
loaded = tf.saved_model.load('my_model')
infer = loaded.signatures['serving_default']
result = infer(tf.constant([[1.0] * 784]))
```

### Serving with REST and gRPC

```bash
# Pull TF Serving Docker image
docker pull tensorflow/serving

# Start serving
docker run -p 8501:8501 -p 8500:8500 \
  --mount type=bind,source=/path/to/my_model,target=/models/my_model \
  -e MODEL_NAME=my_model \
  tensorflow/serving
```

```python
# REST API inference
import requests
import json
import numpy as np

data = json.dumps({
    "signature_name": "serving_default",
    "instances": np.random.randn(1, 784).tolist()
})

response = requests.post(
    'http://localhost:8501/v1/models/my_model:predict',
    data=data,
    headers={"content-type": "application/json"}
)
predictions = response.json()['predictions']

# gRPC inference (faster, binary protocol)
import grpc
from tensorflow_serving.apis import predict_pb2, prediction_service_pb2_grpc

channel = grpc.insecure_channel('localhost:8500')
stub = prediction_service_pb2_grpc.PredictionServiceStub(channel)

request = predict_pb2.PredictRequest()
request.model_spec.name = 'my_model'
request.model_spec.signature_name = 'serving_default'
request.inputs['input'].CopyFrom(tf.make_tensor_proto(data, shape=[1, 784]))

result = stub.Predict(request, timeout=10.0)
```

### Batching and Performance Tuning

```protobuf
# batching_config.proto
max_batch_size { value: 128 }
batch_timeout_micros { value: 5000 }
max_enqueued_batches { value: 10 }
num_batch_threads { value: 4 }
```

```bash
docker run -p 8501:8501 \
  --mount type=bind,source=/path/to/model,target=/models/model \
  --mount type=bind,source=/path/to/batching_config,target=/configs/batching \
  -e MODEL_NAME=model \
  tensorflow/serving \
  --enable_batching=true \
  --batching_parameters_file=/configs/batching
```

### Model Versioning and A/B Testing

```
models/
└── my_model/
    ├── 1/          # Version 1
    │   └── saved_model.pb
    ├── 2/          # Version 2 (latest, served by default)
    │   └── saved_model.pb
    └── 3/          # Version 3
        └── saved_model.pb
```

```protobuf
# model_config.list - serve multiple versions for A/B testing
model_config_list {
  config {
    name: 'my_model'
    base_path: '/models/my_model'
    model_platform: 'tensorflow'
    model_version_policy {
      specific {
        versions: 2
        versions: 3
      }
    }
    version_labels {
      key: 'stable'
      value: 2
    }
    version_labels {
      key: 'canary'
      value: 3
    }
  }
}
```

---

## TFX (TensorFlow Extended) Pipeline

### Pipeline Components

```
┌──────────────────────────────────────────────────────────────┐
│                    TFX Pipeline Flow                           │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│ ExampleGen → StatisticsGen → SchemaGen → ExampleValidator    │
│      ↓                                        ↓              │
│ Transform → Trainer → Tuner → Evaluator → Pusher            │
│                                                              │
│ All connected via ML Metadata (artifact tracking)            │
└──────────────────────────────────────────────────────────────┘
```

```python
import tfx
from tfx.components import (
    CsvExampleGen, StatisticsGen, SchemaGen, ExampleValidator,
    Transform, Trainer, Evaluator, Pusher
)
from tfx.orchestration.experimental.interactive.interactive_context import InteractiveContext

# Create pipeline context
context = InteractiveContext()

# 1. ExampleGen: Ingest data
example_gen = CsvExampleGen(input_base='data/')
context.run(example_gen)

# 2. StatisticsGen: Compute data statistics
statistics_gen = StatisticsGen(examples=example_gen.outputs['examples'])
context.run(statistics_gen)

# 3. SchemaGen: Infer schema
schema_gen = SchemaGen(statistics=statistics_gen.outputs['statistics'])
context.run(schema_gen)

# 4. ExampleValidator: Validate data against schema
example_validator = ExampleValidator(
    statistics=statistics_gen.outputs['statistics'],
    schema=schema_gen.outputs['schema']
)
context.run(example_validator)

# 5. Transform: Feature engineering
transform = Transform(
    examples=example_gen.outputs['examples'],
    schema=schema_gen.outputs['schema'],
    module_file='transform_module.py'
)
context.run(transform)

# 6. Trainer: Train model
trainer = Trainer(
    module_file='trainer_module.py',
    examples=transform.outputs['transformed_examples'],
    transform_graph=transform.outputs['transform_graph'],
    schema=schema_gen.outputs['schema'],
    train_args=tfx.proto.TrainArgs(num_steps=1000),
    eval_args=tfx.proto.EvalArgs(num_steps=100)
)
context.run(trainer)

# 7. Evaluator: Evaluate model quality
evaluator = Evaluator(
    examples=example_gen.outputs['examples'],
    model=trainer.outputs['model'],
    baseline_model=previous_model,
    eval_config=eval_config
)
context.run(evaluator)

# 8. Pusher: Deploy if evaluation passes
pusher = Pusher(
    model=trainer.outputs['model'],
    model_blessing=evaluator.outputs['blessing'],
    push_destination=tfx.proto.PushDestination(
        filesystem=tfx.proto.PushDestination.Filesystem(
            base_directory='serving_model/'
        )
    )
)
context.run(pusher)
```

---

## TensorFlow Lite

### Model Conversion

```python
# Basic conversion
converter = tf.lite.TFLiteConverter.from_saved_model('saved_model_dir')
tflite_model = converter.convert()

with open('model.tflite', 'wb') as f:
    f.write(tflite_model)

# From Keras model
converter = tf.lite.TFLiteConverter.from_keras_model(model)
tflite_model = converter.convert()
```

### Quantization

```python
# Post-training dynamic range quantization (smallest model)
converter = tf.lite.TFLiteConverter.from_saved_model('saved_model_dir')
converter.optimizations = [tf.lite.Optimize.DEFAULT]
tflite_model = converter.convert()
# Weights: float32 → int8, Activations: float32 at runtime

# Post-training full integer quantization (fastest inference)
def representative_dataset():
    for data in calibration_data.take(100):
        yield [data]

converter = tf.lite.TFLiteConverter.from_saved_model('saved_model_dir')
converter.optimizations = [tf.lite.Optimize.DEFAULT]
converter.representative_dataset = representative_dataset
converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
converter.inference_input_type = tf.uint8
converter.inference_output_type = tf.uint8
tflite_model = converter.convert()

# Quantization-aware training (best accuracy)
import tensorflow_model_optimization as tfmot

quantize_model = tfmot.quantization.keras.quantize_model
q_aware_model = quantize_model(model)
q_aware_model.compile(optimizer='adam', loss='sparse_categorical_crossentropy')
q_aware_model.fit(train_data, epochs=3)

# Convert QAT model
converter = tf.lite.TFLiteConverter.from_keras_model(q_aware_model)
converter.optimizations = [tf.lite.Optimize.DEFAULT]
tflite_model = converter.convert()
```

### Delegate Acceleration

```python
# GPU Delegate
import tensorflow as tf

interpreter = tf.lite.Interpreter(
    model_path='model.tflite',
    experimental_delegates=[tf.lite.experimental.load_delegate('libtensorflowlite_gpu_delegate.so')]
)

# NNAPI Delegate (Android)
interpreter = tf.lite.Interpreter(
    model_path='model.tflite',
    experimental_delegates=[tf.lite.experimental.load_delegate('libnnapi_delegate.so')]
)

# CoreML Delegate (iOS)
# Configured via CocoaPods/Swift Package Manager
```

### On-Device Inference

```python
# Python inference (testing)
interpreter = tf.lite.Interpreter(model_path='model.tflite')
interpreter.allocate_tensors()

input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()

# Set input
input_data = np.array(np.random.random_sample(input_details[0]['shape']), dtype=np.float32)
interpreter.set_tensor(input_details[0]['index'], input_data)

# Run inference
interpreter.invoke()

# Get output
output_data = interpreter.get_tensor(output_details[0]['index'])
```

**Quantization Comparison:**

| Method | Size Reduction | Speed | Accuracy Loss |
|--------|---------------|-------|---------------|
| No quantization | 1x | 1x | None |
| Dynamic range | ~4x | ~2-3x | Minimal |
| Full integer (PTQ) | ~4x | ~3-4x | Small |
| Float16 | ~2x | ~1.5x (GPU) | Negligible |
| QAT + integer | ~4x | ~3-4x | Minimal |

---

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│               TensorFlow Production Architecture                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────┐    ┌──────────────┐    ┌──────────────────┐       │
│  │ Client  │ →  │ Load Balancer│ →  │ TF Serving       │       │
│  └─────────┘    └──────────────┘    │ (Docker/K8s)     │       │
│                                     │ ├── Model v1     │       │
│                                     │ ├── Model v2     │       │
│                                     │ └── Batching     │       │
│                                     └──────────────────┘       │
│                                              ↑                  │
│  ┌──────────────────────────────────────────┘                  │
│  │                                                             │
│  │  ┌──────────┐   ┌──────────┐   ┌──────────┐               │
│  │  │ TFX      │ → │ Model    │ → │ Model    │               │
│  └──│ Pipeline │   │ Registry │   │ Push     │               │
│     └──────────┘   └──────────┘   └──────────┘               │
│                                                                 │
│  Mobile/Edge:                                                   │
│  ┌─────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │ TF Lite │ →  │ On-device    │ →  │ Inference    │          │
│  │ Model   │    │ Runtime      │    │ (low latency)│          │
│  └─────────┘    └──────────────┘    └──────────────┘          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```
