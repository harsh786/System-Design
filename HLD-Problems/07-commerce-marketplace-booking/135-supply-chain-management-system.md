# Problem 135: Design Supply Chain Management System

## Problem Statement

Design a comprehensive supply chain management system that optimizes the flow of goods
from suppliers through warehouses to end customers. The platform must provide demand
forecasting, inventory optimization, purchase order management, warehouse operations,
and end-to-end supply chain visibility with real-time tracking and disruption detection.

## Key Challenges

1. **Demand Forecasting**: Build ML-based time-series forecasting (ARIMA, Prophet,
   DeepAR) incorporating seasonality, promotions, weather, and external events with
   hierarchical reconciliation across SKU, category, and region levels.
2. **Inventory Optimization**: Calculate optimal safety stock, reorder points, and
   economic order quantity (EOQ) across a multi-echelon supply network to minimize
   holding costs while maintaining service levels.
3. **Purchase Order Management**: Automate PO creation, approval workflows, supplier
   communication, receiving, and three-way matching (PO, receipt, invoice).
4. **Supplier Management**: Score and rank suppliers on quality, lead time, cost, and
   reliability with automated diversification to reduce single-source risk.
5. **Warehouse Management**: Optimize slotting (bin assignment by pick frequency),
   wave planning for batch picking, put-away algorithms, and cycle counting.
6. **Logistics and Shipment Tracking**: Track shipments across carriers with milestone
   events, ETA prediction, exception handling, and last-mile delivery optimization.
7. **Supply Chain Visibility**: Provide end-to-end visibility from raw material to
   delivery with real-time dashboards, alerts, and drill-down capabilities.
8. **Disruption Detection and Mitigation**: Detect supply chain disruptions (supplier
   failure, port congestion, weather events) early and suggest alternative sourcing
   or routing to minimize impact.

## Scale Requirements

- 10M+ SKUs across product catalog
- 1,000+ warehouses and distribution centers globally
- Real-time inventory accuracy across all locations
- Forecast accuracy >85% at SKU-location level (MAPE <15%)
- 100K+ purchase orders processed daily
- Shipment tracking for 10M+ parcels in transit
- <5 minute latency for inventory updates

## Expected Discussion Areas

- Multi-echelon inventory optimization algorithms
- Demand sensing vs demand forecasting trade-offs
- Bullwhip effect mitigation strategies
- Digital twin simulation for scenario planning
- ABC/XYZ classification for inventory segmentation
- Vendor-managed inventory (VMI) integration
- Reverse logistics and returns processing
