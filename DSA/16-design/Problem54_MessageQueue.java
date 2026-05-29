import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/**
 * Problem 54: In-Memory Message Queue with Topics, Partitions, Consumer Groups
 * 
 * PRODUCTION MAPPING: Apache Kafka, AWS SQS/SNS, RabbitMQ, Azure Event Hubs
 * 
 * Design Decisions:
 * - Topic -> Partitions -> Messages (Kafka model)
 * - Consumer Groups: each message consumed by exactly one consumer per group
 * - Offset tracking per consumer group per partition
 * - Round-robin partition assignment for producers (or key-based)
 * - Rebalancing on consumer join/leave
 * 
 * Trade-offs:
 * - Partition count fixed at creation (Kafka behavior) - scaling requires repartition
 * - At-least-once delivery: consumer must commit offset after processing
 * - Ordering guaranteed within partition, not across partitions
 * 
 * Complexity:
 * - Produce: O(1)
 * - Consume: O(1) per message
 * - Commit: O(1)
 */
public class Problem54_MessageQueue {

    static class Message {
        final String key;
        final String value;
        final long timestamp;
        final Map<String, String> headers;

        Message(String key, String value) {
            this.key = key;
            this.value = value;
            this.timestamp = System.currentTimeMillis();
            this.headers = new HashMap<>();
        }

        @Override
        public String toString() { return "Msg{" + key + "=" + value + "}"; }
    }

    static class Partition {
        private final int id;
        private final List<Message> log = new ArrayList<>(); // append-only log

        Partition(int id) { this.id = id; }

        synchronized int append(Message msg) {
            log.add(msg);
            return log.size() - 1; // return offset
        }

        synchronized Message read(int offset) {
            if (offset < 0 || offset >= log.size()) return null;
            return log.get(offset);
        }

        synchronized int size() { return log.size(); }
    }

    static class Topic {
        final String name;
        final List<Partition> partitions;
        private final AtomicInteger roundRobin = new AtomicInteger(0);

        Topic(String name, int numPartitions) {
            this.name = name;
            this.partitions = new ArrayList<>();
            for (int i = 0; i < numPartitions; i++) {
                partitions.add(new Partition(i));
            }
        }

        /**
         * Determine partition: by key hash or round-robin if key is null
         */
        int getPartition(String key) {
            if (key == null) {
                return roundRobin.getAndIncrement() % partitions.size();
            }
            return Math.abs(key.hashCode()) % partitions.size();
        }
    }

    static class ConsumerGroup {
        final String groupId;
        final Map<Integer, Long> committedOffsets = new ConcurrentHashMap<>(); // partition -> offset
        final Map<String, Set<Integer>> assignments = new ConcurrentHashMap<>(); // consumerId -> partitions

        ConsumerGroup(String groupId) { this.groupId = groupId; }
    }

    static class MessageBroker {
        private final Map<String, Topic> topics = new ConcurrentHashMap<>();
        private final Map<String, ConsumerGroup> consumerGroups = new ConcurrentHashMap<>();

        // ---- Topic Management ----
        public Topic createTopic(String name, int partitions) {
            Topic topic = new Topic(name, partitions);
            topics.put(name, topic);
            return topic;
        }

        // ---- Producer API ----
        public int produce(String topicName, String key, String value) {
            Topic topic = topics.get(topicName);
            if (topic == null) throw new IllegalArgumentException("Topic not found: " + topicName);
            
            int partitionId = topic.getPartition(key);
            Message msg = new Message(key, value);
            return topic.partitions.get(partitionId).append(msg);
        }

        // ---- Consumer Group Management ----
        public void createConsumerGroup(String groupId) {
            consumerGroups.put(groupId, new ConsumerGroup(groupId));
        }

        public void subscribe(String groupId, String topicName, String consumerId) {
            ConsumerGroup group = consumerGroups.get(groupId);
            Topic topic = topics.get(topicName);
            if (group == null || topic == null) throw new IllegalArgumentException();

            group.assignments.putIfAbsent(consumerId, ConcurrentHashMap.newKeySet());
            rebalance(group, topic);
        }

        /**
         * Simple round-robin partition assignment (like Kafka's RangeAssignor)
         */
        private void rebalance(ConsumerGroup group, Topic topic) {
            List<String> consumers = new ArrayList<>(group.assignments.keySet());
            // Clear old assignments
            consumers.forEach(c -> group.assignments.get(c).clear());
            
            // Round-robin assign partitions to consumers
            for (int i = 0; i < topic.partitions.size(); i++) {
                String consumer = consumers.get(i % consumers.size());
                group.assignments.get(consumer).add(i);
            }
        }

        // ---- Consumer API ----
        public List<Message> poll(String topicName, String groupId, String consumerId, int maxMessages) {
            Topic topic = topics.get(topicName);
            ConsumerGroup group = consumerGroups.get(groupId);
            Set<Integer> assignedPartitions = group.assignments.get(consumerId);
            
            List<Message> result = new ArrayList<>();
            if (assignedPartitions == null) return result;

            for (int partId : assignedPartitions) {
                long offset = group.committedOffsets.getOrDefault(partId, 0L);
                Partition partition = topic.partitions.get(partId);
                
                while (result.size() < maxMessages && offset < partition.size()) {
                    Message msg = partition.read((int) offset);
                    if (msg != null) result.add(msg);
                    offset++;
                }
                // Auto-advance offset (at-most-once). For at-least-once, use explicit commit.
                group.committedOffsets.put(partId, offset);
            }
            return result;
        }

        public void commitOffset(String groupId, int partition, long offset) {
            ConsumerGroup group = consumerGroups.get(groupId);
            group.committedOffsets.put(partition, offset);
        }

        public Topic getTopic(String name) { return topics.get(name); }
    }

    public static void main(String[] args) {
        System.out.println("=== In-Memory Message Queue (Kafka-like) ===\n");

        MessageBroker broker = new MessageBroker();

        // Test 1: Create topic and produce messages
        broker.createTopic("orders", 3);
        broker.produce("orders", "user-1", "order-100");
        broker.produce("orders", "user-2", "order-101");
        broker.produce("orders", "user-1", "order-102"); // same partition as first
        System.out.println("PASS: Produced 3 messages to 'orders' topic");

        // Test 2: Key-based partitioning (same key -> same partition)
        Topic orders = broker.getTopic("orders");
        int p1 = orders.getPartition("user-1");
        int p2 = orders.getPartition("user-1");
        assert p1 == p2 : "Same key must map to same partition";
        System.out.println("PASS: Same key routes to same partition (" + p1 + ")");

        // Test 3: Consumer group with single consumer
        broker.createConsumerGroup("payment-service");
        broker.subscribe("payment-service", "orders", "consumer-1");
        List<Message> messages = broker.poll("orders", "payment-service", "consumer-1", 10);
        assert messages.size() == 3 : "Single consumer should get all messages, got: " + messages.size();
        System.out.println("PASS: Single consumer gets all 3 messages");

        // Test 4: Second poll returns nothing (offsets committed)
        messages = broker.poll("orders", "payment-service", "consumer-1", 10);
        assert messages.isEmpty() : "Should get nothing after committed";
        System.out.println("PASS: No duplicate delivery after offset commit");

        // Test 5: Multiple consumer groups (each gets all messages independently)
        broker.createConsumerGroup("analytics-service");
        broker.subscribe("analytics-service", "orders", "analytics-1");
        messages = broker.poll("orders", "analytics-service", "analytics-1", 10);
        assert messages.size() == 3 : "Different group should get all messages";
        System.out.println("PASS: Independent consumer groups get their own copy");

        // Test 6: Consumer group with multiple consumers (partition assignment)
        broker.createTopic("events", 4);
        for (int i = 0; i < 20; i++) {
            broker.produce("events", "key-" + i, "event-" + i);
        }
        broker.createConsumerGroup("processors");
        broker.subscribe("processors", "events", "proc-1");
        broker.subscribe("processors", "events", "proc-2");
        
        List<Message> m1 = broker.poll("events", "processors", "proc-1", 20);
        List<Message> m2 = broker.poll("events", "processors", "proc-2", 20);
        assert m1.size() + m2.size() == 20 : "Both consumers together should get all messages";
        assert !m1.isEmpty() && !m2.isEmpty() : "Work should be distributed";
        System.out.printf("PASS: 2 consumers split work: %d + %d = 20\n", m1.size(), m2.size());

        // Test 7: Ordering within partition
        broker.createTopic("ordered", 1); // single partition = total order
        broker.produce("ordered", null, "first");
        broker.produce("ordered", null, "second");
        broker.produce("ordered", null, "third");
        broker.createConsumerGroup("ordered-group");
        broker.subscribe("ordered-group", "ordered", "c1");
        messages = broker.poll("ordered", "ordered-group", "c1", 10);
        assert messages.get(0).value.equals("first");
        assert messages.get(1).value.equals("second");
        assert messages.get(2).value.equals("third");
        System.out.println("PASS: Ordering preserved within partition");

        System.out.println("\nAll tests passed!");
    }
}
