# Autonomous Systems

## Overview

Autonomous systems (self-driving vehicles, robots, drones) represent safety-critical ML applications where failures can cause physical harm. They require real-time multi-modal perception, robust decision-making under uncertainty, and rigorous safety engineering.

---

## 1. Self-Driving Car ML Stack

```
┌─────────────────────────────────────────────────────────────┐
│              AUTONOMOUS DRIVING STACK                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  SENSORS                                                     │
│  ┌────────┐ ┌───────┐ ┌───────┐ ┌────────────┐            │
│  │Cameras │ │ LiDAR │ │ Radar │ │Ultrasonics │            │
│  │(6-12)  │ │(1-5)  │ │(4-6)  │ │(8-12)     │            │
│  └───┬────┘ └──┬────┘ └──┬────┘ └─────┬──────┘            │
│      └──────────┴─────────┴────────────┘                    │
│                         │                                    │
│                         ▼                                    │
│  ┌──────────────────────────────────────────┐               │
│  │          PERCEPTION                       │               │
│  │  • 3D Object Detection                   │               │
│  │  • Semantic Segmentation                  │               │
│  │  • Lane Detection                         │               │
│  │  • Traffic Sign/Light Recognition         │               │
│  │  • Free Space Estimation                  │               │
│  └─────────────────────┬────────────────────┘               │
│                         │                                    │
│                         ▼                                    │
│  ┌──────────────────────────────────────────┐               │
│  │          PREDICTION                       │               │
│  │  • Object Tracking                        │               │
│  │  • Trajectory Forecasting                 │               │
│  │  • Intent Prediction                      │               │
│  └─────────────────────┬────────────────────┘               │
│                         │                                    │
│                         ▼                                    │
│  ┌──────────────────────────────────────────┐               │
│  │          PLANNING                         │               │
│  │  • Route Planning                         │               │
│  │  • Behavior Planning (lane change, etc.)  │               │
│  │  • Motion Planning (trajectory generation)│               │
│  └─────────────────────┬────────────────────┘               │
│                         │                                    │
│                         ▼                                    │
│  ┌──────────────────────────────────────────┐               │
│  │          CONTROL                          │               │
│  │  • Steering, Throttle, Brake             │               │
│  │  • PID / MPC Controllers                  │               │
│  └──────────────────────────────────────────┘               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Sensor Suite & Fusion

| Sensor | Range | Resolution | Weather | Cost |
|--------|-------|-----------|---------|------|
| Camera | 200m+ | High (pixels) | Degrades in rain/fog | Low |
| LiDAR | 200m | High (3D points) | Degrades in heavy rain | High |
| Radar | 300m+ | Low | All-weather | Medium |
| Ultrasonic | 5m | Low | Good | Low |

### Fusion Strategies

- **Early fusion**: Raw sensor data combined before processing
- **Late fusion**: Independent detections merged (NMS across modalities)
- **Mid/Deep fusion**: Feature-level fusion (BEVFusion approach)

```python
class BEVFusionModel(nn.Module):
    """Bird's Eye View fusion of camera + LiDAR"""
    
    def __init__(self):
        self.camera_encoder = ResNet50()  # Image features
        self.lidar_encoder = PointPillars()  # Point cloud features
        self.lift_splat = LiftSplatShoot()  # Camera → BEV projection
        self.fusion = ConvFusionBlock()  # Merge BEV features
        self.detection_head = CenterPointHead()  # 3D detection
    
    def forward(self, images, points):
        # Camera branch: images → BEV features
        cam_feats = self.camera_encoder(images)
        cam_bev = self.lift_splat(cam_feats)
        
        # LiDAR branch: points → BEV features
        lidar_bev = self.lidar_encoder(points)
        
        # Fusion in BEV space
        fused = self.fusion(torch.cat([cam_bev, lidar_bev], dim=1))
        
        # Detection
        return self.detection_head(fused)
```

---

## 3. 3D Object Detection

### Key Architectures

| Model | Input | Approach | Speed |
|-------|-------|----------|-------|
| PointPillars | LiDAR | Pillar-based encoding | Fast |
| CenterPoint | LiDAR | Center heatmap + attributes | Fast |
| PointRCNN | LiDAR | Point-based proposals | Medium |
| BEVFusion | Camera+LiDAR | BEV feature fusion | Medium |
| DETR3D | Camera only | Transformer queries in 3D | Medium |
| UniAD | All | End-to-end unified model | Slow |

### Evaluation Metrics

- **mAP** (mean Average Precision) at various IoU thresholds
- **NDS** (nuScenes Detection Score): composite of mAP + TP metrics
- **TP metrics**: ATE (translation), ASE (scale), AOE (orientation), AVE (velocity)

---

## 4. HD Mapping & Localization

- **HD Maps**: Lane boundaries, traffic signs, road topology (centimeter accuracy)
- **Localization**: Match sensor data to HD map (LiDAR-based, visual localization)
- **Online mapping**: Real-time map construction (MapTR, HDMapNet)
- **SLAM**: Simultaneous Localization and Mapping for unmapped areas

---

## 5. Behavior Prediction (Trajectory Forecasting)

```python
class TrajectoryPredictor(nn.Module):
    """Multi-modal trajectory prediction"""
    
    def __init__(self, n_modes=6, horizon=6):  # 6 modes, 6 seconds
        super().__init__()
        self.agent_encoder = AgentHistoryEncoder()  # Past trajectories
        self.map_encoder = VectorMapEncoder()  # Lane graph
        self.interaction = CrossAttention()  # Agent-agent, agent-map
        self.decoder = MultiModalDecoder(n_modes, horizon)
    
    def forward(self, agent_history, map_polylines, agent_mask):
        # Encode agent histories
        agent_feats = self.agent_encoder(agent_history)
        
        # Encode map context
        map_feats = self.map_encoder(map_polylines)
        
        # Model interactions
        fused = self.interaction(agent_feats, map_feats)
        
        # Predict K possible futures with probabilities
        trajectories, probabilities = self.decoder(fused)
        # trajectories: [batch, K, T, 2]  (x,y for each timestep)
        # probabilities: [batch, K]
        return trajectories, probabilities
```

### Key Methods

- **VectorNet**: Polyline-based map + trajectory encoding
- **LaneGCN**: Lane graph convolution for map reasoning
- **HiVT**: Hierarchical vector transformer
- **Motion Transformer**: Transformer-based multi-agent prediction

---

## 6. Path Planning

### Approaches

| Type | Methods | Pros | Cons |
|------|---------|------|------|
| Sampling-based | RRT, lattice | Completeness guarantees | Slow in high-D |
| Optimization-based | TrajOpt, iLQR | Smooth trajectories | Local minima |
| Learning-based | Imitation, RL | Handles complex scenarios | Hard to verify safety |
| Hybrid | ChauffeurNet | Combines learned + rules | Complex system |

### Safety Constraints in Planning

- Collision avoidance (hard constraint)
- Traffic rules compliance
- Comfort (jerk/acceleration limits)
- Progress toward goal
- Uncertainty-aware (keep safe distance based on prediction uncertainty)

---

## 7. Robotics

### Manipulation & Grasping

- **Grasp detection**: Predict grasp poses from depth images
- **6-DOF grasp planning**: SE(3) grasp pose prediction
- **Sim-to-real**: Train in simulation, deploy on real robot
- **Foundation models**: RT-2, SayCan (language-conditioned manipulation)

### Navigation

- **Classical**: SLAM + A* / D*
- **Learning-based**: End-to-end from sensors to controls
- **Hybrid**: Learned perception + classical planning

---

## 8. Drone Autonomy

- **Visual SLAM**: ORB-SLAM3, VINS-Mono
- **Obstacle avoidance**: Depth estimation + potential fields
- **Trajectory optimization**: Minimum snap/jerk trajectories
- **Multi-drone coordination**: Formation control, task allocation
- **Applications**: Inspection, delivery, mapping, agriculture

---

## 9. Sim-to-Real Transfer

```
┌─────────────────────────────────────────────┐
│          SIM-TO-REAL PIPELINE                │
├─────────────────────────────────────────────┤
│                                              │
│  Simulator (CARLA, Isaac, etc.)             │
│  ┌────────────────────────────────┐         │
│  │ Domain Randomization:          │         │
│  │ • Lighting, textures, colors   │         │
│  │ • Object shapes/sizes          │         │
│  │ • Physics parameters           │         │
│  │ • Sensor noise models          │         │
│  └──────────────┬─────────────────┘         │
│                 │                            │
│                 ▼                            │
│  ┌────────────────────────────────┐         │
│  │ Train Policy in Diverse Sim    │         │
│  └──────────────┬─────────────────┘         │
│                 │                            │
│                 ▼                            │
│  ┌────────────────────────────────┐         │
│  │ Domain Adaptation (optional):  │         │
│  │ • CycleGAN (sim→real images)   │         │
│  │ • Feature alignment            │         │
│  │ • Progressive fine-tuning      │         │
│  └──────────────┬─────────────────┘         │
│                 │                            │
│                 ▼                            │
│  Real World Deployment                      │
│  (with safety monitors)                     │
└─────────────────────────────────────────────┘
```

---

## 10. Safety Engineering

### Functional Safety (ISO 26262)

- **ASIL levels**: A (lowest) to D (highest) risk classification
- **Redundancy**: Dual/triple redundant compute, sensors, actuators
- **Fault detection**: Runtime monitoring, watchdog timers
- **Safe states**: Minimal risk condition (pull over, stop)

### SOTIF (ISO 21448)

Safety Of The Intended Functionality — addresses insufficiencies in the system design:
- Known unsafe scenarios → mitigate through design
- Unknown unsafe scenarios → discover through testing/analysis
- ML-specific: handling novel/OOD scenarios

### Safety Analysis Framework

```
┌─────────────────────────────────────────────┐
│         SAFETY ANALYSIS FRAMEWORK            │
├─────────────────────────────────────────────┤
│                                              │
│  1. Hazard Analysis (HARA)                  │
│     └─▶ Identify hazardous events           │
│                                              │
│  2. ASIL Determination                      │
│     └─▶ Severity × Exposure × Control       │
│                                              │
│  3. Safety Goals                            │
│     └─▶ Top-level safety requirements       │
│                                              │
│  4. Safety Architecture                     │
│     └─▶ Redundancy, monitoring, fallback    │
│                                              │
│  5. ML Safety Requirements                  │
│     ├─▶ OOD detection thresholds            │
│     ├─▶ Uncertainty calibration             │
│     ├─▶ Adversarial robustness              │
│     └─▶ Performance monitoring              │
│                                              │
│  6. V&V (Verification & Validation)         │
│     ├─▶ Simulation testing (billions of mi) │
│     ├─▶ Closed-course testing               │
│     ├─▶ Public road testing                 │
│     └─▶ Shadow mode deployment              │
│                                              │
└─────────────────────────────────────────────┘
```

---

## 11. Verification & Validation for ML

- **Simulation testing**: CARLA, SUMO, Waymax (billions of scenarios)
- **Corner case generation**: Adversarial scenario generation
- **Formal methods**: Bounded verification of neural networks (limited)
- **Runtime monitoring**: OOD detection, prediction consistency checks
- **Metrics**: Miles between disengagements, collision rate per mile

---

## 12. Edge Computing & Real-time Constraints

| Component | Latency Budget | Typical Hardware |
|-----------|---------------|-----------------|
| Perception | 50-100ms | GPU (Orin, A100) |
| Prediction | 20-50ms | GPU |
| Planning | 50-100ms | CPU/GPU |
| Control | 5-10ms | Real-time CPU |
| **Total** | **<200ms** | |

### Optimization Techniques

- Model quantization (INT8, FP16)
- TensorRT / ONNX Runtime optimization
- Pruning and knowledge distillation
- Operator fusion and custom CUDA kernels
- Temporal caching (reuse previous frame features)

---

## Production Considerations

- **Determinism**: Same inputs must produce same outputs (reproducibility)
- **Graceful degradation**: Sensor failure → reduced capability, not crash
- **OTA updates**: Over-the-air model updates with rollback capability
- **Data logging**: Record all sensor data for incident analysis
- **Telemetry**: Fleet-level performance monitoring
- **Regulatory compliance**: Region-specific driving rules

---

## Interview Questions

1. **Compare early, mid, and late fusion strategies for autonomous driving. When would you use each?**
2. **How would you handle a LiDAR failure at highway speeds? Design the fallback system.**
3. **Explain the sim-to-real gap. What techniques reduce it?**
4. **Design a trajectory prediction system for a busy intersection with pedestrians, cyclists, and vehicles.**
5. **How do you validate an ML-based perception system for safety-critical deployment?**
6. **What is SOTIF and how does it differ from functional safety (ISO 26262)?**
7. **How would you detect out-of-distribution inputs in a self-driving car's perception system?**
8. **Design the real-time compute architecture for an L4 autonomous vehicle.**

---

## Key Papers

1. **"PointPillars"** - Lang et al. (2019) - Fast 3D detection from point clouds
2. **"CenterPoint"** - Yin et al. (2021) - Center-based 3D object detection
3. **"BEVFusion"** - Liu et al. (2023) - Multi-modal BEV fusion
4. **"VectorNet"** - Gao et al. (2020) - Vectorized scene representation
5. **"UniAD"** - Hu et al. (2023) - Unified end-to-end autonomous driving
6. **"ChauffeurNet"** - Bansal et al. (2019) - Imitation learning for driving
7. **"Domain Randomization"** - Tobin et al. (2017) - Sim-to-real transfer
8. **"RT-2"** - Brohan et al. (2023) - Vision-language-action model for robotics

---

## Common Pitfalls

1. **Overfitting to simulation**: Sim performance ≠ real-world performance
2. **Long tail of edge cases**: 99% accuracy is not enough for safety
3. **Ignoring sensor degradation**: Rain, fog, dirt on lenses
4. **Static evaluation**: Testing on fixed datasets misses temporal issues
5. **Neglecting system-level interactions**: Perception error → planning error amplification
6. **Underestimating latency**: End-to-end latency matters more than component latency
