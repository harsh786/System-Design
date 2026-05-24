# Amazon SQS Learning Notes

This folder contains notes for learning and designing production systems with Amazon SQS.

## Files

- [SQS production scaling and comparison](./SQS_PRODUCTION_SCALING_AND_COMPARISON.md): Production scaling checklist, use cases, weak-fit scenarios, and SQS vs Kafka vs RabbitMQ comparison.
- [SQS scalability and parallel processing](./SQS_SCALABILITY_AND_PARALLEL_PROCESSING.md): How SQS handles millions of messages, how standard and FIFO queue parallelism works, and how to scale consumers safely.
- [AWS SQS delayed processing architecture](./AWS_SQS_DELAYED_PROCESSING_ARCHITECTURE.md): Multi-queue delayed processing architecture with retry design.
- [Single queue delayed processing](./SINGLE_QUEUE_DELAYED_PROCESSING.md): Delayed processing with one SQS queue using message delay, visibility timeout, and external state.
