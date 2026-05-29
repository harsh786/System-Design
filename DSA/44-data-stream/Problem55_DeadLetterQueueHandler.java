import java.util.*;
import java.util.concurrent.atomic.*;

/**
 * Problem 55: Dead Letter Queue Handler
 * 
 * Production Relevance:
 * - Essential for handling poison pills (messages that always fail processing)
 * - Prevents infinite retry loops that block partition consumption
 * - Used in Kafka (DLQ topics), SQS (DLQ), RabbitMQ (dead letter exchanges)
 * - Enables async investigation of failures without blocking the main pipeline
 * 
 * Architect Considerations:
 * - Retry policy: exponential backoff with max retries before DLQ
 * - DLQ must preserve original message metadata (headers, timestamp, source topic)
 * - Need monitoring/alerting on DLQ depth
 * - Reprocessing: ability to replay DLQ messages back to source after fix
 */
public class Problem55_DeadLetterQueueHandler {

    static class Message {
        String id;
        String payload;
        Map<String, String> headers;
        int retryCount;
        long firstAttemptTs;
        String failureReason;

        Message(String id, String payload) {
            this.id = id;
            this.payload = payload;
            this.headers = new HashMap<>();
            this.retryCount = 0;
        }

        Message withRetry(String reason) {
            this.retryCount++;
            this.failureReason = reason;
            if (firstAttemptTs == 0) firstAttemptTs = System.currentTimeMillis();
            return this;
        }
    }

    static class DLQEntry {
        Message original;
        String sourceTopic;
        int partition;
        long offset;
        String errorClass;
        String errorMessage;
        long deadLetteredAt;

        DLQEntry(Message msg, String source, int partition, long offset, String errorClass, String errorMsg) {
            this.original = msg;
            this.sourceTopic = source;
            this.partition = partition;
            this.offset = offset;
            this.errorClass = errorClass;
            this.errorMessage = errorMsg;
            this.deadLetteredAt = System.currentTimeMillis();
        }
    }

    interface MessageProcessor {
        void process(Message msg) throws Exception;
    }

    static class RetryWithDLQ {
        private final int maxRetries;
        private final long[] backoffMs; // Exponential backoff schedule
        private final Queue<DLQEntry> dlq = new LinkedList<>();
        private final AtomicLong successCount = new AtomicLong(0);
        private final AtomicLong dlqCount = new AtomicLong(0);

        RetryWithDLQ(int maxRetries) {
            this.maxRetries = maxRetries;
            this.backoffMs = new long[maxRetries];
            for (int i = 0; i < maxRetries; i++) {
                backoffMs[i] = (long) Math.pow(2, i) * 100; // 100, 200, 400, 800...
            }
        }

        public boolean processWithRetry(Message msg, MessageProcessor processor,
                                         String sourceTopic, int partition, long offset) {
            for (int attempt = 0; attempt <= maxRetries; attempt++) {
                try {
                    processor.process(msg);
                    successCount.incrementAndGet();
                    return true;
                } catch (Exception e) {
                    msg.withRetry(e.getMessage());
                    if (attempt < maxRetries) {
                        try { Thread.sleep(backoffMs[attempt]); } catch (InterruptedException ie) {
                            Thread.currentThread().interrupt();
                        }
                    } else {
                        // Send to DLQ
                        DLQEntry entry = new DLQEntry(msg, sourceTopic, partition, offset,
                                e.getClass().getSimpleName(), e.getMessage());
                        dlq.offer(entry);
                        dlqCount.incrementAndGet();
                    }
                }
            }
            return false;
        }

        // Replay DLQ messages (after bug fix deployed)
        public List<Message> replayDLQ(int maxMessages) {
            List<Message> replayed = new ArrayList<>();
            for (int i = 0; i < maxMessages && !dlq.isEmpty(); i++) {
                DLQEntry entry = dlq.poll();
                entry.original.retryCount = 0; // Reset for reprocessing
                replayed.add(entry.original);
            }
            return replayed;
        }

        public int getDLQDepth() { return dlq.size(); }
        public long getSuccessCount() { return successCount.get(); }
        public long getDLQCount() { return dlqCount.get(); }
    }

    public static void main(String[] args) {
        System.out.println("=== Dead Letter Queue Handler ===\n");

        RetryWithDLQ handler = new RetryWithDLQ(3);

        // Processor that fails on certain messages (poison pills)
        MessageProcessor processor = msg -> {
            if (msg.payload.contains("POISON")) {
                throw new RuntimeException("Cannot parse malformed payload");
            }
            if (msg.payload.contains("TRANSIENT") && msg.retryCount < 2) {
                throw new RuntimeException("Temporary network error");
            }
        };

        // Process mix of good, transient-error, and poison messages
        String[][] messages = {
            {"msg-1", "normal payload"},
            {"msg-2", "TRANSIENT failure then ok"},
            {"msg-3", "POISON pill message"},
            {"msg-4", "another normal"},
            {"msg-5", "POISON again"},
        };

        for (int i = 0; i < messages.length; i++) {
            Message msg = new Message(messages[i][0], messages[i][1]);
            boolean success = handler.processWithRetry(msg, processor, "orders-topic", 0, i);
            System.out.printf("%-30s -> %s (retries: %d)%n",
                    messages[i][1], success ? "SUCCESS" : "DLQ", msg.retryCount);
        }

        System.out.printf("%nSuccess: %d, DLQ: %d, DLQ depth: %d%n",
                handler.getSuccessCount(), handler.getDLQCount(), handler.getDLQDepth());

        // Replay DLQ
        System.out.println("\n--- Replaying DLQ after fix ---");
        List<Message> replayed = handler.replayDLQ(10);
        System.out.println("Messages to reprocess: " + replayed.size());
    }
}
