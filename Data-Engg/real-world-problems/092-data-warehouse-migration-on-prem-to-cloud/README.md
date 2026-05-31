# Problem 92: Data Warehouse Migration (On-Prem to Cloud)

### Problem 92: Data Warehouse Migration (On-Prem to Cloud)
```
PHASES:
  1. Assessment: Map all tables, queries, users, dependencies
  2. Dual-write: Replicate to cloud (CDC), compare outputs
  3. Validation: Run same queries on both, ensure results match
  4. Cutover: Switch applications to cloud, monitor
  5. Decommission: Turn off on-prem after 30-day bake period
TIMELINE: 6-18 months for enterprise (1000+ tables)
```
