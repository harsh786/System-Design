# Problem 80: Data Platform for Autonomous Vehicles

### Problem 80: Data Platform for Autonomous Vehicles
```
SCALE: 1 car = 1TB/hour (cameras, lidar, radar, GPS)
ARCH: Edge (car) → 5G upload → S3 → Spark (labeling, training) → Model deploy
STORAGE: 1 PB/day across fleet (object store + metadata DB)
CHALLENGE: Selecting important data (not all data is useful for training)
```
