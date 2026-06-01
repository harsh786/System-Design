# Convolutional Neural Networks (CNNs)

## 1. Convolution Operation

### Intuition
Convolution slides a small filter (kernel) over the input, computing dot products at each position. This exploits:
- **Local connectivity**: each neuron connects only to a local region
- **Weight sharing**: same filter applied everywhere → translation equivariance
- **Hierarchical features**: early layers detect edges, later layers detect objects

### 1D Convolution

```
Input:    [1, 2, 3, 4, 5, 6, 7]    (length 7)
Kernel:   [1, 0, -1]                (length 3)

Output:   [1·1+2·0+3·(-1), 2·1+3·0+4·(-1), ...]
        = [-2, -2, -2, -2, -2]       (length 5 = 7-3+1)
```

### 2D Convolution (Core of CNNs)

```
Input (5×5):                    Kernel (3×3):
┌───┬───┬───┬───┬───┐         ┌───┬───┬───┐
│ 1 │ 0 │ 1 │ 0 │ 1 │         │ 1 │ 0 │-1 │
├───┼───┼───┼───┼───┤         ├───┼───┼───┤
│ 0 │ 1 │ 0 │ 1 │ 0 │         │ 1 │ 0 │-1 │
├───┼───┼───┼───┼───┤         ├───┼───┼───┤
│ 1 │ 0 │ 1 │ 0 │ 1 │         │ 1 │ 0 │-1 │
├───┼───┼───┼───┼───┤         └───┴───┴───┘
│ 0 │ 1 │ 0 │ 1 │ 0 │
├───┼───┼───┼───┼───┤
│ 1 │ 0 │ 1 │ 0 │ 1 │
└───┴───┴───┴───┴───┘

Position (0,0): 1·1 + 0·0 + 1·(-1) + 0·1 + 1·0 + 0·(-1) + 1·1 + 0·0 + 1·(-1) = 0
Position (0,1): 0·1 + 1·0 + 0·(-1) + 1·1 + 0·0 + 1·(-1) + 0·1 + 1·0 + 0·(-1) = 0

Output (3×3): stride=1, no padding → (5-3)/1 + 1 = 3
```

### Convolution Step-by-Step (ASCII)

```
Step 1:                     Step 2:                     Step 3:
┌─────────┐───┬───┐       ┌───┌─────────┐───┐       ┌───┬───┌─────────┐
│ x  x  x │   │   │       │   │ x  x  x │   │       │   │   │ x  x  x │
│ x  x  x │   │   │  →    │   │ x  x  x │   │  →    │   │   │ x  x  x │
│ x  x  x │   │   │       │   │ x  x  x │   │       │   │   │ x  x  x │
└─────────┘───┴───┘       └───└─────────┘───┘       └───┴───└─────────┘
│   │   │   │   │         │   │   │   │   │         │   │   │   │   │
│   │   │   │   │         │   │   │   │   │         │   │   │   │   │
└───┴───┴───┴───┘         └───┴───┴───┴───┘         └───┴───┴───┴───┘
     ↓                          ↓                          ↓
  out[0,0]                   out[0,1]                   out[0,2]
```

### Output Size Formula

```
Output_size = ⌊(Input_size - Kernel_size + 2·Padding) / Stride⌋ + 1
```

| Input | Kernel | Padding | Stride | Output |
|-------|--------|---------|--------|--------|
| 32×32 | 3×3 | 0 | 1 | 30×30 |
| 32×32 | 3×3 | 1 | 1 | 32×32 (same) |
| 32×32 | 3×3 | 1 | 2 | 16×16 |
| 224×224 | 7×7 | 3 | 2 | 112×112 |

## 2. Padding, Stride, Pooling

### Padding Types
- **Valid (no padding)**: Output shrinks
- **Same**: Pad so output = input size (pad = k//2 for stride=1)
- **Causal**: For 1D, pad only left side (temporal causality)

### Pooling Operations

```
Max Pooling (2×2, stride 2):          Average Pooling (2×2):
┌───┬───┬───┬───┐                    ┌───┬───┬───┬───┐
│ 1 │ 3 │ 2 │ 1 │                    │ 1 │ 3 │ 2 │ 1 │
├───┼───┼───┼───┤  → ┌───┬───┐      ├───┼───┼───┼───┤  → ┌─────┬─────┐
│ 4 │ 2 │ 5 │ 3 │    │ 4 │ 5 │      │ 4 │ 2 │ 5 │ 3 │    │ 2.5 │ 2.75│
├───┼───┼───┼───┤    ├───┼───┤      ├───┼───┼───┼───┤    ├─────┼─────┤
│ 1 │ 0 │ 3 │ 2 │    │ 1 │ 3 │      │ 1 │ 0 │ 3 │ 2 │    │ 0.5 │ 2.5 │
├───┼───┼───┼───┤    └───┴───┘      ├───┼───┼───┼───┤    └─────┴─────┘
│ 0 │ 1 │ 1 │ 2 │                    │ 0 │ 1 │ 1 │ 2 │
└───┴───┴───┴───┘                    └───┴───┴───┴───┘
```

- **Max Pooling**: Takes maximum value → preserves strongest feature
- **Average Pooling**: Takes mean → smoother, used as final global pooling
- **Global Average Pooling (GAP)**: Average entire feature map to single value → replaces fully connected layers

## 3. Feature Maps and Multi-Channel Convolution

```
Input: C_in channels (e.g., RGB = 3)
Kernel: C_in × K × K (one 2D kernel per input channel)
One filter produces: 1 output feature map (sum across channels)
C_out filters → C_out output feature maps

Parameters per conv layer = C_out × (C_in × K × K + 1)
                                                    ↑ bias
```

```python
import torch.nn as nn

# Conv2d: in_channels, out_channels, kernel_size
conv = nn.Conv2d(3, 64, kernel_size=3, stride=1, padding=1)
# Parameters: 64 × (3 × 3 × 3 + 1) = 64 × 28 = 1,792

# Input: [batch, 3, 224, 224] → Output: [batch, 64, 224, 224]
```

## 4. CNN Architectures

### Architecture Timeline

```
1998: LeNet-5        → 5 layers, 60K params
2012: AlexNet        → 8 layers, 60M params, ReLU, Dropout, GPU
2014: VGGNet         → 16-19 layers, 138M params, 3×3 convs only
2014: GoogLeNet      → 22 layers, 6.8M params, Inception modules
2015: ResNet         → 152 layers, skip connections
2017: DenseNet       → Dense connections
2019: EfficientNet   → NAS-designed, compound scaling
2020: Vision Transformer → Patches + self-attention (not CNN!)
```

### LeNet-5 (LeCun, 1998)

```
Input(32×32×1) → Conv(5×5,6) → Pool(2×2) → Conv(5×5,16) → Pool(2×2) → FC(120) → FC(84) → FC(10)
```

### AlexNet (2012) - Started the Deep Learning Revolution

```
Input(227×227×3)
  → Conv(11×11, 96, stride=4) → ReLU → MaxPool → LRN
  → Conv(5×5, 256, pad=2) → ReLU → MaxPool → LRN
  → Conv(3×3, 384) → ReLU
  → Conv(3×3, 384) → ReLU
  → Conv(3×3, 256) → ReLU → MaxPool
  → FC(4096) → Dropout → FC(4096) → Dropout → FC(1000)
```

Key innovations: ReLU, Dropout, Data Augmentation, GPU training

### VGGNet (2014) - Simplicity & Depth

Insight: Stack many 3×3 convs instead of large kernels (two 3×3 = one 5×5 receptive field, fewer params)

```python
# VGG-16 in PyTorch
vgg16 = nn.Sequential(
    # Block 1: 2× Conv(3×3, 64) + MaxPool
    nn.Conv2d(3, 64, 3, padding=1), nn.ReLU(),
    nn.Conv2d(64, 64, 3, padding=1), nn.ReLU(),
    nn.MaxPool2d(2, 2),
    # Block 2: 2× Conv(3×3, 128) + MaxPool
    nn.Conv2d(64, 128, 3, padding=1), nn.ReLU(),
    nn.Conv2d(128, 128, 3, padding=1), nn.ReLU(),
    nn.MaxPool2d(2, 2),
    # ... blocks 3-5
    # FC layers
    nn.Flatten(),
    nn.Linear(512*7*7, 4096), nn.ReLU(), nn.Dropout(),
    nn.Linear(4096, 4096), nn.ReLU(), nn.Dropout(),
    nn.Linear(4096, 1000),
)
```

### ResNet (2015) - Skip Connections

**Problem**: Very deep networks degrade (not overfit—training loss increases!)

**Solution**: Residual learning — learn F(x) = H(x) - x instead of H(x) directly

```
Residual Block:
                    ┌────────────────────┐
                    │    Identity (x)     │
                    │                    │
x ──→ [Conv-BN-ReLU-Conv-BN] ──→ (+) ──→ ReLU ──→ output
       └── F(x) ──────────────┘   ↑
                                   x (skip connection)

Output = ReLU(F(x) + x)
```

```python
class ResidualBlock(nn.Module):
    def __init__(self, channels):
        super().__init__()
        self.conv1 = nn.Conv2d(channels, channels, 3, padding=1)
        self.bn1 = nn.BatchNorm2d(channels)
        self.conv2 = nn.Conv2d(channels, channels, 3, padding=1)
        self.bn2 = nn.BatchNorm2d(channels)
    
    def forward(self, x):
        residual = x
        out = F.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        out += residual  # Skip connection!
        return F.relu(out)
```

**Why it works**: Gradient flows directly through skip connections → solves vanishing gradient in deep networks.

### Inception/GoogLeNet (2014)

Idea: Apply multiple kernel sizes in parallel, let network choose.

```
              Input
         ╱    │    │    ╲
      1×1   1×1  1×1  MaxPool
       │     │    │     3×3
       │   3×3  5×5    1×1
       │     │    │      │
       └──── Concat ─────┘
              │
           Output
```

### EfficientNet (2019)

Compound scaling: scale depth, width, and resolution together.
```
depth:  d = α^φ
width:  w = β^φ
resolution: r = γ^φ
subject to: α·β²·γ² ≈ 2

EfficientNet-B0 → B7 by increasing φ
```

## 5. Transfer Learning

```python
import torchvision.models as models

# Load pretrained ResNet
model = models.resnet50(weights='IMAGENET1K_V2')

# Strategy 1: Feature extraction (freeze all, replace head)
for param in model.parameters():
    param.requires_grad = False
model.fc = nn.Linear(2048, num_classes)  # Only train this

# Strategy 2: Fine-tuning (unfreeze last few layers)
for param in model.layer4.parameters():
    param.requires_grad = True

# Strategy 3: Full fine-tuning with small LR
optimizer = torch.optim.Adam([
    {'params': model.layer4.parameters(), 'lr': 1e-4},
    {'params': model.fc.parameters(), 'lr': 1e-3},
], lr=1e-5)  # Base LR for frozen layers
```

### When to Use Which Strategy

| Scenario | Strategy |
|----------|----------|
| Small dataset, similar domain | Feature extraction |
| Small dataset, different domain | Fine-tune later layers |
| Large dataset, similar domain | Full fine-tuning, small LR |
| Large dataset, different domain | Train from scratch or full fine-tune |

## 6. Object Detection

### YOLO (You Only Look Once)

```
Input Image → CNN Backbone → Grid (S×S) → Each cell predicts:
  - B bounding boxes (x, y, w, h, confidence)
  - C class probabilities

Single forward pass → real-time detection!

Architecture (simplified):
Image(448×448) → Conv layers → 7×7×30 output
  30 = 2 boxes × 5 values + 20 classes (Pascal VOC)
```

### R-CNN Family Evolution

```
R-CNN (2014):       Selective Search → Crop regions → CNN each → SVM classify
                    (2000 crops per image, very slow)

Fast R-CNN (2015):  Image → CNN → Feature map → RoI Pooling → FC → class + box
                    (share computation, but still external proposals)

Faster R-CNN (2016): Image → CNN → Feature map → RPN (Region Proposal Network) → RoI → heads
                     (end-to-end, proposals learned)
```

```
Faster R-CNN Architecture:
┌──────────────────────────────────────────┐
│ Input Image                               │
└────────────────────┬─────────────────────┘
                     ↓
┌──────────────────────────────────────────┐
│ Backbone CNN (ResNet/FPN)                 │
└────────────────────┬─────────────────────┘
                     ↓
            ┌────────┴────────┐
            ↓                 ↓
    ┌──────────────┐   ┌──────────────┐
    │     RPN      │   │ Feature Maps │
    │ (proposals)  │   │              │
    └──────┬───────┘   └──────┬───────┘
           └────────┬─────────┘
                    ↓
         ┌──────────────────┐
         │   RoI Pooling    │
         └────────┬─────────┘
                  ↓
         ┌────────┴────────┐
         ↓                 ↓
  ┌─────────────┐  ┌─────────────┐
  │Classification│  │  Bounding   │
  │    Head      │  │  Box Head   │
  └─────────────┘  └─────────────┘
```

## 7. Image Segmentation

### U-Net Architecture (2015)

```
Encoder (Downsampling)              Decoder (Upsampling)
                    
[572×572×1]                         [388×388×2]
    ↓ Conv×2                             ↑ Conv×2
[568×568×64]─────────────────copy──→[392×392×128]
    ↓ MaxPool                            ↑ UpConv
[284×284×64]                        [196×196×128]
    ↓ Conv×2                             ↑ Conv×2
[280×280×128]────────────────copy──→[200×200×256]
    ↓ MaxPool                            ↑ UpConv
[140×140×128]                       [100×100×256]
    ↓ Conv×2                             ↑ Conv×2
[136×136×256]────────────────copy──→[104×104×512]
    ↓ MaxPool                            ↑ UpConv
[68×68×256]                          [52×52×512]
    ↓ Conv×2                             ↑ Conv×2
[64×64×512]──────────────────copy──→[56×56×1024]
    ↓ MaxPool                            ↑ UpConv
[32×32×512]                          [28×28×1024]
    ↓ Conv×2
[28×28×1024]─────── Bottleneck ──────┘
```

Key: Skip connections concatenate encoder features with decoder → preserves spatial detail.

### Mask R-CNN

Extends Faster R-CNN with a parallel mask prediction branch:
- Classification head → class label
- Box regression head → bounding box
- **Mask head** → pixel-level segmentation within each RoI

## 8. Modern Techniques

### Depthwise Separable Convolution (MobileNet)

Standard conv: C_in × C_out × K × K params
Depthwise separable: C_in × K × K + C_in × C_out params (8-9× fewer!)

```python
# Depthwise separable conv
depthwise = nn.Conv2d(C_in, C_in, 3, padding=1, groups=C_in)  # Each channel independently
pointwise = nn.Conv2d(C_in, C_out, 1)  # 1×1 conv to mix channels
```

### Data Augmentation for Vision

```python
from torchvision import transforms

train_transform = transforms.Compose([
    transforms.RandomResizedCrop(224),
    transforms.RandomHorizontalFlip(),
    transforms.ColorJitter(brightness=0.2, contrast=0.2),
    transforms.RandomRotation(15),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    transforms.RandomErasing(p=0.1),
])
```

### Modern training recipe (from papers like "ResNet strikes back"):
- RandAugment / TrivialAugment
- Mixup / CutMix
- Label Smoothing (0.1)
- Stochastic Depth (drop layers randomly)
- Cosine LR schedule with warmup
- EMA (Exponential Moving Average) of weights

## Production Considerations

1. **Model size**: MobileNet/EfficientNet for mobile, ResNet for servers
2. **Quantization**: INT8 for 2-4× speedup with minimal accuracy loss
3. **ONNX export**: Framework-agnostic deployment
4. **Batched inference**: Maximize GPU utilization
5. **TensorRT/CoreML**: Platform-specific optimization

```python
# Export to ONNX
torch.onnx.export(model, dummy_input, "model.onnx", opset_version=17)

# Quantization
model_int8 = torch.quantization.quantize_dynamic(model, {nn.Linear, nn.Conv2d}, dtype=torch.qint8)
```

## Interview Questions

1. **Why 3×3 convolutions?** Two 3×3 convs = 5×5 receptive field with fewer params (18 vs 25) and more nonlinearity.

2. **How do skip connections help?** Allow gradient to flow directly to earlier layers, enabling training of very deep networks.

3. **What's the receptive field of a CNN?** The region of input that affects a given output neuron. Grows with depth: after L layers of 3×3, RF = 1 + 2L.

4. **Why does max pooling work for classification but not segmentation?** Max pool discards spatial information. Segmentation needs pixel-level precision → use skip connections (U-Net) or dilated convolutions.

5. **1×1 convolution—what does it do?** Channel-wise linear combination. Used for dimensionality reduction/expansion without changing spatial size.

6. **How does Faster R-CNN differ from YOLO?** Faster R-CNN: two-stage (propose then classify), more accurate. YOLO: single-stage, faster but less precise on small objects.

7. **What makes EfficientNet efficient?** Compound scaling (balanced depth/width/resolution) found via NAS. Better accuracy/FLOP tradeoff.

8. **Explain depthwise separable convolution.** Factorize standard conv into depthwise (per-channel spatial) + pointwise (1×1 cross-channel). ~9× fewer operations.
