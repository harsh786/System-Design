# TensorFlow Mastery

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     TensorFlow Ecosystem                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                     tf.keras (High-Level API)                    │   │
│  │  Sequential │ Functional │ Subclassing                          │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────────┐     │
│  │ tf.data  │  │tf.function│  │tf.saved  │  │ tf.distribute     │     │
│  │(Pipeline)│  │  (Graph) │  │  model   │  │ (Multi-GPU/TPU)   │     │
│  └──────────┘  └──────────┘  └──────────┘  └───────────────────┘     │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    Deployment                                    │   │
│  │  TF Serving │ TFLite │ TF.js │ TFX Pipeline                    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

## TF2 and Keras High-Level API

```python
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, Model
import numpy as np

print(f"TensorFlow version: {tf.__version__}")
print(f"GPU available: {tf.config.list_physical_devices('GPU')}")

# GPU memory growth (prevent OOM)
gpus = tf.config.list_physical_devices('GPU')
for gpu in gpus:
    tf.config.experimental.set_memory_growth(gpu, True)
```

## Sequential vs Functional API vs Subclassing

### Sequential API (Simple stack of layers)

```python
model = keras.Sequential([
    layers.Input(shape=(224, 224, 3)),
    layers.Conv2D(32, 3, activation='relu', padding='same'),
    layers.BatchNormalization(),
    layers.MaxPooling2D(),
    layers.Conv2D(64, 3, activation='relu', padding='same'),
    layers.BatchNormalization(),
    layers.MaxPooling2D(),
    layers.GlobalAveragePooling2D(),
    layers.Dense(256, activation='relu'),
    layers.Dropout(0.5),
    layers.Dense(10, activation='softmax'),
])

model.compile(
    optimizer=keras.optimizers.Adam(learning_rate=1e-3),
    loss='sparse_categorical_crossentropy',
    metrics=['accuracy']
)

model.summary()
```

### Functional API (Multi-input/output, shared layers, DAGs)

```python
# Multi-input model
image_input = keras.Input(shape=(224, 224, 3), name='image')
metadata_input = keras.Input(shape=(10,), name='metadata')

# Image branch
x = layers.Conv2D(32, 3, activation='relu')(image_input)
x = layers.GlobalAveragePooling2D()(x)
x = layers.Dense(64, activation='relu')(x)

# Metadata branch
y = layers.Dense(32, activation='relu')(metadata_input)

# Merge
combined = layers.Concatenate()([x, y])
output = layers.Dense(64, activation='relu')(combined)
output = layers.Dense(1, activation='sigmoid', name='prediction')(output)

model = Model(inputs=[image_input, metadata_input], outputs=output)

model.compile(
    optimizer='adam',
    loss='binary_crossentropy',
    metrics=['accuracy', keras.metrics.AUC()]
)

# Residual connections (skip connections)
inputs = keras.Input(shape=(256,))
x = layers.Dense(256, activation='relu')(inputs)
x = layers.Dense(256, activation='relu')(x)
x = layers.Add()([x, inputs])  # Skip connection
output = layers.Dense(10, activation='softmax')(x)
model = Model(inputs, output)
```

### Model Subclassing (Full flexibility)

```python
class ResidualBlock(layers.Layer):
    def __init__(self, filters, stride=1):
        super().__init__()
        self.conv1 = layers.Conv2D(filters, 3, strides=stride, padding='same')
        self.bn1 = layers.BatchNormalization()
        self.conv2 = layers.Conv2D(filters, 3, padding='same')
        self.bn2 = layers.BatchNormalization()
        
        self.shortcut = keras.Sequential()
        if stride != 1:
            self.shortcut = keras.Sequential([
                layers.Conv2D(filters, 1, strides=stride),
                layers.BatchNormalization()
            ])
    
    def call(self, x, training=False):
        residual = self.shortcut(x)
        x = tf.nn.relu(self.bn1(self.conv1(x), training=training))
        x = self.bn2(self.conv2(x), training=training)
        x = tf.nn.relu(x + residual)
        return x


class CustomModel(Model):
    def __init__(self, num_classes):
        super().__init__()
        self.block1 = ResidualBlock(64)
        self.block2 = ResidualBlock(128, stride=2)
        self.pool = layers.GlobalAveragePooling2D()
        self.classifier = layers.Dense(num_classes)
    
    def call(self, x, training=False):
        x = self.block1(x, training=training)
        x = self.block2(x, training=training)
        x = self.pool(x)
        return self.classifier(x)

model = CustomModel(num_classes=10)
model.compile(optimizer='adam', loss=keras.losses.SparseCategoricalCrossentropy(from_logits=True))
```

## tf.data Pipeline

```python
# ============================================================
# HIGH-PERFORMANCE DATA PIPELINE
# ============================================================

# From tensors
dataset = tf.data.Dataset.from_tensor_slices((X, y))

# From files
file_pattern = 'data/train/*.tfrecord'
dataset = tf.data.TFRecordDataset(tf.io.gfile.glob(file_pattern))

# Image loading pipeline
def load_and_preprocess(file_path, label):
    image = tf.io.read_file(file_path)
    image = tf.image.decode_jpeg(image, channels=3)
    image = tf.image.resize(image, [224, 224])
    image = tf.cast(image, tf.float32) / 255.0
    # Data augmentation
    image = tf.image.random_flip_left_right(image)
    image = tf.image.random_brightness(image, max_delta=0.2)
    return image, label

# Optimized pipeline
AUTOTUNE = tf.data.AUTOTUNE
BATCH_SIZE = 32

train_ds = (
    tf.data.Dataset.from_tensor_slices((file_paths, labels))
    .shuffle(buffer_size=10000)
    .map(load_and_preprocess, num_parallel_calls=AUTOTUNE)
    .batch(BATCH_SIZE)
    .prefetch(AUTOTUNE)  # Overlap data loading with training
)

val_ds = (
    tf.data.Dataset.from_tensor_slices((val_paths, val_labels))
    .map(load_and_preprocess, num_parallel_calls=AUTOTUNE)
    .batch(BATCH_SIZE)
    .cache()  # Cache in memory for small datasets
    .prefetch(AUTOTUNE)
)

# TFRecord reading
def parse_tfrecord(serialized):
    features = tf.io.parse_single_example(serialized, {
        'image': tf.io.FixedLenFeature([], tf.string),
        'label': tf.io.FixedLenFeature([], tf.int64),
    })
    image = tf.io.decode_raw(features['image'], tf.float32)
    image = tf.reshape(image, [224, 224, 3])
    return image, features['label']

dataset = (
    tf.data.TFRecordDataset(file_paths, num_parallel_reads=AUTOTUNE)
    .map(parse_tfrecord, num_parallel_calls=AUTOTUNE)
    .shuffle(1000)
    .batch(32)
    .prefetch(AUTOTUNE)
)
```

### tf.data Performance Tips

```
Pipeline Optimization Flow:
┌────────┐    ┌─────────┐    ┌───────┐    ┌──────────┐
│ Read   │───▶│  Map    │───▶│ Batch │───▶│ Prefetch │
│(parallel)   │(parallel)    │       │    │(AUTOTUNE)│
└────────┘    └─────────┘    └───────┘    └──────────┘

Rules:
1. Always use .prefetch(AUTOTUNE)
2. Use .cache() for small datasets that fit in memory
3. .shuffle() BEFORE .batch()
4. Use num_parallel_calls=AUTOTUNE in .map()
5. Use interleave for reading from multiple files
6. Vectorize map operations (batch then map, not map then batch)
```

## Custom Training Loops

```python
# ============================================================
# CUSTOM TRAINING WITH tf.GradientTape
# ============================================================

model = CustomModel(num_classes=10)
optimizer = keras.optimizers.AdamW(learning_rate=1e-3, weight_decay=0.01)
loss_fn = keras.losses.SparseCategoricalCrossentropy(from_logits=True)

# Metrics
train_loss = keras.metrics.Mean()
train_acc = keras.metrics.SparseCategoricalAccuracy()
val_loss = keras.metrics.Mean()
val_acc = keras.metrics.SparseCategoricalAccuracy()

@tf.function  # Compile to graph for speed
def train_step(x, y):
    with tf.GradientTape() as tape:
        logits = model(x, training=True)
        loss = loss_fn(y, logits)
        # Add regularization losses
        loss += sum(model.losses)
    
    gradients = tape.gradient(loss, model.trainable_variables)
    # Gradient clipping
    gradients, _ = tf.clip_by_global_norm(gradients, clip_norm=1.0)
    optimizer.apply_gradients(zip(gradients, model.trainable_variables))
    
    train_loss.update_state(loss)
    train_acc.update_state(y, logits)

@tf.function
def val_step(x, y):
    logits = model(x, training=False)
    loss = loss_fn(y, logits)
    val_loss.update_state(loss)
    val_acc.update_state(y, logits)

# Training loop
for epoch in range(epochs):
    # Reset metrics
    train_loss.reset_state()
    train_acc.reset_state()
    val_loss.reset_state()
    val_acc.reset_state()
    
    for x_batch, y_batch in train_ds:
        train_step(x_batch, y_batch)
    
    for x_batch, y_batch in val_ds:
        val_step(x_batch, y_batch)
    
    print(f"Epoch {epoch+1} | "
          f"Loss: {train_loss.result():.4f} Acc: {train_acc.result():.4f} | "
          f"Val Loss: {val_loss.result():.4f} Val Acc: {val_acc.result():.4f}")
```

## Callbacks

```python
callbacks = [
    # Save best model
    keras.callbacks.ModelCheckpoint(
        'best_model.keras',
        monitor='val_loss',
        save_best_only=True,
        mode='min'
    ),
    
    # Early stopping
    keras.callbacks.EarlyStopping(
        monitor='val_loss',
        patience=10,
        restore_best_weights=True
    ),
    
    # TensorBoard logging
    keras.callbacks.TensorBoard(
        log_dir='./logs',
        histogram_freq=1,
        profile_batch='10,20'  # Profile batches 10-20
    ),
    
    # Learning rate scheduling
    keras.callbacks.ReduceLROnPlateau(
        monitor='val_loss',
        factor=0.5,
        patience=5,
        min_lr=1e-7
    ),
    
    # CSV logging
    keras.callbacks.CSVLogger('training_log.csv'),
]

# Custom callback
class MetricsLogger(keras.callbacks.Callback):
    def on_epoch_end(self, epoch, logs=None):
        # Log to W&B, MLflow, etc.
        wandb.log(logs)

model.fit(
    train_ds,
    validation_data=val_ds,
    epochs=100,
    callbacks=callbacks
)
```

## SavedModel Format

```python
# ============================================================
# SAVING AND LOADING
# ============================================================

# Keras native format (.keras)
model.save('model.keras')
loaded = keras.models.load_model('model.keras')

# SavedModel format (for TF Serving)
model.export('saved_model/')
# Creates: saved_model/saved_model.pb + variables/

# Load SavedModel
loaded = tf.saved_model.load('saved_model/')
infer = loaded.signatures['serving_default']
output = infer(tf.constant(input_data))

# Save weights only
model.save_weights('weights.weights.h5')
model.load_weights('weights.weights.h5')

# Concrete function export (for specific input shapes)
@tf.function(input_signature=[tf.TensorSpec(shape=[None, 224, 224, 3], dtype=tf.float32)])
def serve(input_image):
    return model(input_image, training=False)

tf.saved_model.save(model, 'saved_model/', signatures={'serving_default': serve})
```

## TF Serving for Production

```python
# ============================================================
# TENSORFLOW SERVING DEPLOYMENT
# ============================================================

# Directory structure for versioned models:
# models/
#   my_model/
#     1/                    ← Version 1
#       saved_model.pb
#       variables/
#     2/                    ← Version 2 (auto-loaded)
#       saved_model.pb
#       variables/

# Export model with versioning
version = 2
export_path = f'models/my_model/{version}'
model.export(export_path)
```

```bash
# Run TF Serving with Docker
docker run -p 8501:8501 \
  --mount type=bind,source=/path/to/models,target=/models \
  -e MODEL_NAME=my_model \
  tensorflow/serving

# REST API prediction
curl -X POST http://localhost:8501/v1/models/my_model:predict \
  -H "Content-Type: application/json" \
  -d '{"instances": [[1.0, 2.0, 3.0]]}'
```

```python
# Client code
import requests
import json

def predict(instances):
    url = 'http://localhost:8501/v1/models/my_model:predict'
    payload = json.dumps({"instances": instances})
    response = requests.post(url, data=payload)
    return response.json()['predictions']

# gRPC client (faster for production)
import grpc
from tensorflow_serving.apis import predict_pb2, prediction_service_pb2_grpc

channel = grpc.insecure_channel('localhost:8500')
stub = prediction_service_pb2_grpc.PredictionServiceStub(channel)

request = predict_pb2.PredictRequest()
request.model_spec.name = 'my_model'
request.inputs['input'].CopyFrom(tf.make_tensor_proto(data))
result = stub.Predict(request)
```

## TensorFlow Lite for Mobile/Edge

```python
# ============================================================
# TFLITE CONVERSION
# ============================================================

# Basic conversion
converter = tf.lite.TFLiteConverter.from_saved_model('saved_model/')
tflite_model = converter.convert()

with open('model.tflite', 'wb') as f:
    f.write(tflite_model)

# Quantized conversion (smaller, faster)
converter = tf.lite.TFLiteConverter.from_saved_model('saved_model/')
converter.optimizations = [tf.lite.Optimize.DEFAULT]

# Full integer quantization (requires representative dataset)
def representative_data():
    for i in range(100):
        yield [np.random.randn(1, 224, 224, 3).astype(np.float32)]

converter.representative_dataset = representative_data
converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
converter.inference_input_type = tf.uint8
converter.inference_output_type = tf.uint8

quantized_model = converter.convert()

# TFLite inference
interpreter = tf.lite.Interpreter(model_path='model.tflite')
interpreter.allocate_tensors()

input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()

interpreter.set_tensor(input_details[0]['index'], input_data)
interpreter.invoke()
output = interpreter.get_tensor(output_details[0]['index'])
```

## TFX Pipeline Overview

```
┌────────────────────────────────────────────────────────────────┐
│                    TFX Pipeline Components                      │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ExampleGen → StatisticsGen → SchemaGen → ExampleValidator     │
│       │                                        │               │
│       ▼                                        ▼               │
│  Transform → Trainer → Tuner → Evaluator → Pusher            │
│                                     │                          │
│                              InfraValidator                     │
└────────────────────────────────────────────────────────────────┘
```

```python
# TFX Pipeline definition
import tfx
from tfx.components import (
    CsvExampleGen, StatisticsGen, SchemaGen, ExampleValidator,
    Transform, Trainer, Evaluator, Pusher
)

# Define pipeline
def create_pipeline():
    example_gen = CsvExampleGen(input_base='data/')
    
    statistics_gen = StatisticsGen(examples=example_gen.outputs['examples'])
    
    schema_gen = SchemaGen(statistics=statistics_gen.outputs['statistics'])
    
    transform = Transform(
        examples=example_gen.outputs['examples'],
        schema=schema_gen.outputs['schema'],
        module_file='transform_module.py'
    )
    
    trainer = Trainer(
        module_file='trainer_module.py',
        examples=transform.outputs['transformed_examples'],
        transform_graph=transform.outputs['transform_graph'],
        schema=schema_gen.outputs['schema'],
        train_args=tfx.proto.TrainArgs(num_steps=10000),
        eval_args=tfx.proto.EvalArgs(num_steps=1000)
    )
    
    evaluator = Evaluator(
        examples=example_gen.outputs['examples'],
        model=trainer.outputs['model'],
    )
    
    pusher = Pusher(
        model=trainer.outputs['model'],
        model_blessing=evaluator.outputs['blessing'],
        push_destination=tfx.proto.PushDestination(
            filesystem=tfx.proto.PushDestination.Filesystem(
                base_directory='serving_model/'
            )
        )
    )
    
    return tfx.dsl.Pipeline(
        pipeline_name='my_pipeline',
        components=[example_gen, statistics_gen, schema_gen,
                   transform, trainer, evaluator, pusher]
    )
```

## Distribution Strategies

```python
# ============================================================
# MULTI-GPU / TPU TRAINING
# ============================================================

# MirroredStrategy: Single machine, multiple GPUs
strategy = tf.distribute.MirroredStrategy()
print(f"Number of devices: {strategy.num_replicas_in_sync}")

with strategy.scope():
    model = create_model()
    model.compile(optimizer='adam', loss='sparse_categorical_crossentropy')

# Batch size scales with number of GPUs
GLOBAL_BATCH_SIZE = 64 * strategy.num_replicas_in_sync
train_ds = train_ds.batch(GLOBAL_BATCH_SIZE)

model.fit(train_ds, epochs=10)

# TPUStrategy: For Google Cloud TPUs
resolver = tf.distribute.cluster_resolver.TPUClusterResolver()
tf.config.experimental_connect_to_cluster(resolver)
tf.tpu.experimental.initialize_tpu_system(resolver)
strategy = tf.distribute.TPUStrategy(resolver)

# MultiWorkerMirroredStrategy: Multiple machines
strategy = tf.distribute.MultiWorkerMirroredStrategy()
```

## TensorBoard Visualization

```python
# ============================================================
# TENSORBOARD
# ============================================================

# Basic logging with Keras
tensorboard_cb = keras.callbacks.TensorBoard(log_dir='./logs')
model.fit(train_ds, callbacks=[tensorboard_cb])

# Custom logging with tf.summary
log_dir = 'logs/custom'
writer = tf.summary.create_file_writer(log_dir)

with writer.as_default():
    for step in range(1000):
        tf.summary.scalar('loss', loss_value, step=step)
        tf.summary.scalar('accuracy', acc_value, step=step)
        tf.summary.image('predictions', images, step=step)
        tf.summary.histogram('weights', model.layers[0].weights[0], step=step)

# Launch: tensorboard --logdir=logs/
# Or in notebook: %load_ext tensorboard; %tensorboard --logdir logs/

# Hyperparameter tuning visualization
from tensorboard.plugins.hparams import api as hp

HP_LR = hp.HParam('learning_rate', hp.RealInterval(1e-5, 1e-2))
HP_DROPOUT = hp.HParam('dropout', hp.RealInterval(0.1, 0.5))

with tf.summary.create_file_writer('logs/hparam_tuning').as_default():
    hp.hparams_config(
        hparams=[HP_LR, HP_DROPOUT],
        metrics=[hp.Metric('accuracy', display_name='Accuracy')]
    )
```

## Common Patterns and Anti-Patterns

```python
# ANTI-PATTERN: Not using @tf.function for training steps
def train_step(x, y):  # Runs in eager mode (SLOW)
    ...

# GOOD: Decorate with @tf.function
@tf.function
def train_step(x, y):  # Compiled to graph (FAST)
    ...

# ANTI-PATTERN: Python side effects in @tf.function
@tf.function
def bad_function(x):
    print(x)  # Only prints during tracing, not execution!
    my_list.append(x)  # Won't work as expected

# GOOD: Use tf.print for debugging
@tf.function
def good_function(x):
    tf.print("Value:", x)  # Works correctly

# ANTI-PATTERN: Creating variables inside @tf.function
@tf.function
def bad():
    v = tf.Variable(0)  # Error! Variables must be created outside

# GOOD:
v = tf.Variable(0)
@tf.function
def good():
    v.assign_add(1)
```

## Performance Optimization

```
1. Use tf.data with prefetch(AUTOTUNE)
2. Use @tf.function for all training/inference functions
3. Use mixed precision: keras.mixed_precision.set_global_policy('mixed_float16')
4. Use XLA compilation: tf.function(jit_compile=True)
5. Profile with TensorBoard profiler
6. Use TFRecord format for large datasets
7. Cache small datasets: dataset.cache()
8. Use distribution strategies for multi-GPU
```

## Comparison: model.fit() vs Custom Loop

| Aspect | model.fit() | Custom Loop |
|--------|-------------|-------------|
| Simplicity | High | Low |
| Callbacks | Built-in | Manual |
| Multi-GPU | Automatic | Manual setup |
| Custom losses | Limited | Full control |
| GANs/RL | Difficult | Natural |
| Debugging | Harder | Easier |
| **Use when** | Standard tasks | Custom training logic |
