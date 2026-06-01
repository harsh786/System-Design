# Project 2: Image Classification with CNN

## What You'll Learn
- Building CNNs from scratch with PyTorch
- Data augmentation techniques
- Training loops with validation
- Learning rate scheduling
- Model evaluation and confusion matrices

## Architecture

```
┌──────────┐    ┌──────────────┐    ┌─────────────┐    ┌──────────┐
│ CIFAR-10 │───►│ Augmentation │───►│ CNN Model   │───►│ Training │
│ Dataset  │    │ Pipeline     │    │ (3 Conv +   │    │ Loop     │
└──────────┘    └──────────────┘    │  2 FC)      │    └──────────┘
                                    └─────────────┘         │
                                                            ▼
                                    ┌─────────────┐    ┌──────────┐
                                    │ Per-class   │◄───│ Evaluate │
                                    │ Metrics     │    │ on Test  │
                                    └─────────────┘    └──────────┘
```

## CNN Architecture
```
Input (3x32x32)
  → Conv2d(3,32) + BN + ReLU + MaxPool
  → Conv2d(32,64) + BN + ReLU + MaxPool
  → Conv2d(64,128) + BN + ReLU + MaxPool
  → Flatten → FC(512) → Dropout → FC(10)
```

## Prerequisites

```bash
pip install torch torchvision numpy
```

## How to Run

```bash
python image_classifier.py
```

## Expected Output
- Training progress with loss/accuracy per epoch
- Test accuracy (~75-85% in 10 epochs)
- Per-class accuracy breakdown

## Extension Ideas
- Use pretrained ResNet with transfer learning
- Add Grad-CAM visualization
- Export to ONNX for deployment
