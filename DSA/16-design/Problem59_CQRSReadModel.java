import java.util.*;
import java.util.concurrent.*;
import java.util.function.*;

/**
 * Problem 59: CQRS Read Model (Eventual Consistency, Projections)
 * 
 * PRODUCTION MAPPING: Axon Framework, EventStore projections, Kafka Streams KTables,
 *                     DynamoDB streams + Lambda projections, materialized views
 * 
 * CQRS: Command Query Responsibility Segregation
 * - Write side: event sourced, normalized, optimized for writes
 * - Read side: denormalized, optimized for specific query patterns
 * - Projections: transform events into read models asynchronously
 * 
 * Design Decisions:
 * - Async projection processing (eventual consistency)
 * - Multiple read models from same event stream (one per query pattern)
 * - Projection position tracking (resume from last processed)
 * - Rebuild capability (drop and replay)
 * 
 * Trade-offs:
 * - Eventual consistency: reads may be stale
 * - Multiple read models: storage cost vs query performance
 * - Rebuild time: grows with event count (mitigated by snapshots)
 */
public class Problem59_CQRSReadModel {

    // ---- Write Side (Events) ----
    static class DomainEvent {
        final String id = UUID.randomUUID().toString();
        final String aggregateId;
        final String type;
        final Map<String, Object> data;
        final long timestamp;
        final long position; // global ordering

        DomainEvent(String aggregateId, String type, Map<String, Object> data, long position) {
            this.aggregateId = aggregateId;
            this.type = type;
            this.data = data;
            this.timestamp = System.currentTimeMillis();
            this.position = position;
        }
    }

    static class EventLog {
        private final List<DomainEvent> events = new CopyOnWriteArrayList<>();
        private long nextPosition = 1;
        private final List<Consumer<DomainEvent>> listeners = new CopyOnWriteArrayList<>();

        public synchronized DomainEvent append(String aggregateId, String type, Map<String, Object> data) {
            DomainEvent event = new DomainEvent(aggregateId, type, data, nextPosition++);
            events.add(event);
            for (Consumer<DomainEvent> l : listeners) l.accept(event);
            return event;
        }

        public List<DomainEvent> getEventsFrom(long position) {
            List<DomainEvent> result = new ArrayList<>();
            for (DomainEvent e : events) {
                if (e.position >= position) result.add(e);
            }
            return result;
        }

        public void subscribe(Consumer<DomainEvent> listener) { listeners.add(listener); }
        public long getLatestPosition() { return nextPosition - 1; }
    }

    // ---- Read Side (Projections) ----
    interface Projection {
        String getName();
        void handle(DomainEvent event);
        long getLastProcessedPosition();
        void reset(); // for rebuild
    }

    /**
     * Order Summary Projection: denormalized view for "get order details" query
     */
    static class OrderSummaryProjection implements Projection {
        // Read model: orderId -> summary
        final Map<String, OrderSummary> summaries = new ConcurrentHashMap<>();
        private long lastPosition = 0;

        static class OrderSummary {
            String orderId, customerId, status;
            double totalAmount;
            List<String> items = new ArrayList<>();
            long lastUpdated;
        }

        @Override
        public void handle(DomainEvent event) {
            switch (event.type) {
                case "OrderCreated": {
                    OrderSummary s = new OrderSummary();
                    s.orderId = event.aggregateId;
                    s.customerId = (String) event.data.get("customerId");
                    s.status = "CREATED";
                    s.totalAmount = 0;
                    s.lastUpdated = event.timestamp;
                    summaries.put(event.aggregateId, s);
                    break;
                }
                case "ItemAdded": {
                    OrderSummary s = summaries.get(event.aggregateId);
                    if (s != null) {
                        s.items.add((String) event.data.get("item"));
                        s.totalAmount += ((Number) event.data.get("price")).doubleValue();
                        s.lastUpdated = event.timestamp;
                    }
                    break;
                }
                case "OrderConfirmed": {
                    OrderSummary s = summaries.get(event.aggregateId);
                    if (s != null) { s.status = "CONFIRMED"; s.lastUpdated = event.timestamp; }
                    break;
                }
                case "OrderShipped": {
                    OrderSummary s = summaries.get(event.aggregateId);
                    if (s != null) { s.status = "SHIPPED"; s.lastUpdated = event.timestamp; }
                    break;
                }
            }
            lastPosition = event.position;
        }

        @Override public String getName() { return "OrderSummary"; }
        @Override public long getLastProcessedPosition() { return lastPosition; }
        @Override public void reset() { summaries.clear(); lastPosition = 0; }
    }

    /**
     * Customer Orders Projection: "get all orders for customer" query
     */
    static class CustomerOrdersProjection implements Projection {
        // customerId -> list of order IDs
        final Map<String, List<String>> customerOrders = new ConcurrentHashMap<>();
        private long lastPosition = 0;

        @Override
        public void handle(DomainEvent event) {
            if ("OrderCreated".equals(event.type)) {
                String customerId = (String) event.data.get("customerId");
                customerOrders.computeIfAbsent(customerId, k -> new CopyOnWriteArrayList<>())
                    .add(event.aggregateId);
            }
            lastPosition = event.position;
        }

        @Override public String getName() { return "CustomerOrders"; }
        @Override public long getLastProcessedPosition() { return lastPosition; }
        @Override public void reset() { customerOrders.clear(); lastPosition = 0; }
    }

    // ---- Projection Engine ----
    static class ProjectionEngine {
        private final EventLog eventLog;
        private final List<Projection> projections = new ArrayList<>();
        private final ScheduledExecutorService executor;

        public ProjectionEngine(EventLog eventLog) {
            this.eventLog = eventLog;
            this.executor = Executors.newSingleThreadScheduledExecutor(r -> {
                Thread t = new Thread(r, "projection-engine");
                t.setDaemon(true);
                return t;
            });
        }

        public void register(Projection projection) {
            projections.add(projection);
        }

        /** Process events synchronously (for testing) */
        public void processSync() {
            for (Projection p : projections) {
                List<DomainEvent> events = eventLog.getEventsFrom(p.getLastProcessedPosition() + 1);
                for (DomainEvent e : events) {
                    p.handle(e);
                }
            }
        }

        /** Start async processing */
        public void startAsync(long intervalMs) {
            executor.scheduleAtFixedRate(this::processSync, 0, intervalMs, TimeUnit.MILLISECONDS);
        }

        /** Rebuild a projection from scratch */
        public void rebuild(Projection projection) {
            projection.reset();
            List<DomainEvent> allEvents = eventLog.getEventsFrom(1);
            for (DomainEvent e : allEvents) {
                projection.handle(e);
            }
        }

        public long getLag(Projection p) {
            return eventLog.getLatestPosition() - p.getLastProcessedPosition();
        }

        public void shutdown() { executor.shutdown(); }
    }

    public static void main(String[] args) throws InterruptedException {
        System.out.println("=== CQRS Read Model ===\n");

        EventLog eventLog = new EventLog();
        ProjectionEngine engine = new ProjectionEngine(eventLog);
        OrderSummaryProjection orderSummary = new OrderSummaryProjection();
        CustomerOrdersProjection customerOrders = new CustomerOrdersProjection();
        engine.register(orderSummary);
        engine.register(customerOrders);

        // Test 1: Write events and project
        eventLog.append("order-1", "OrderCreated", Map.of("customerId", "cust-A"));
        eventLog.append("order-1", "ItemAdded", Map.of("item", "Widget", "price", 29.99));
        eventLog.append("order-1", "ItemAdded", Map.of("item", "Gadget", "price", 49.99));
        eventLog.append("order-1", "OrderConfirmed", Map.of());

        engine.processSync();

        OrderSummaryProjection.OrderSummary summary = orderSummary.summaries.get("order-1");
        assert summary != null;
        assert summary.status.equals("CONFIRMED");
        assert Math.abs(summary.totalAmount - 79.98) < 0.01;
        assert summary.items.size() == 2;
        System.out.println("PASS: Order summary projection correct (total=$79.98, CONFIRMED)");

        // Test 2: Customer orders projection
        eventLog.append("order-2", "OrderCreated", Map.of("customerId", "cust-A"));
        engine.processSync();
        
        List<String> custAOrders = customerOrders.customerOrders.get("cust-A");
        assert custAOrders != null && custAOrders.size() == 2;
        System.out.println("PASS: Customer orders projection shows 2 orders for cust-A");

        // Test 3: Eventual consistency (lag)
        eventLog.append("order-2", "ItemAdded", Map.of("item", "Doohickey", "price", 9.99));
        long lag = engine.getLag(orderSummary);
        assert lag == 1 : "Should have lag of 1";
        engine.processSync();
        lag = engine.getLag(orderSummary);
        assert lag == 0;
        System.out.println("PASS: Lag tracking works (caught up after processSync)");

        // Test 4: Rebuild projection from scratch
        orderSummary.reset();
        assert orderSummary.summaries.isEmpty();
        engine.rebuild(orderSummary);
        summary = orderSummary.summaries.get("order-1");
        assert summary != null && summary.status.equals("CONFIRMED");
        System.out.println("PASS: Projection rebuild from scratch");

        // Test 5: Multiple read models from same events
        assert orderSummary.summaries.size() == 2; // 2 orders
        assert customerOrders.customerOrders.get("cust-A").size() == 2;
        System.out.println("PASS: Multiple projections from same event stream");

        // Test 6: Async projection processing
        engine.startAsync(20);
        eventLog.append("order-1", "OrderShipped", Map.of());
        Thread.sleep(50); // wait for async processing
        summary = orderSummary.summaries.get("order-1");
        assert summary.status.equals("SHIPPED");
        System.out.println("PASS: Async projection processes events");

        engine.shutdown();
        System.out.println("\nAll tests passed!");
    }
}
