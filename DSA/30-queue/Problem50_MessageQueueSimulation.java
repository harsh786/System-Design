import java.util.*;
import java.util.concurrent.*;

public class Problem50_MessageQueueSimulation {
    static class Message { String topic; String payload; long timestamp; Message(String t, String p) { topic = t; payload = p; timestamp = System.currentTimeMillis(); } }
    static class MessageQueue {
        Map<String, Queue<Message>> topics = new ConcurrentHashMap<>();
        Map<String, List<String>> subscriptions = new ConcurrentHashMap<>();
        void createTopic(String topic) { topics.putIfAbsent(topic, new ConcurrentLinkedQueue<>()); }
        void publish(String topic, String payload) {
            createTopic(topic);
            topics.get(topic).offer(new Message(topic, payload));
        }
        void subscribe(String consumer, String topic) {
            subscriptions.computeIfAbsent(consumer, k -> new ArrayList<>()).add(topic);
        }
        Message consume(String consumer) {
            List<String> subs = subscriptions.getOrDefault(consumer, Collections.emptyList());
            for (String topic : subs) {
                Queue<Message> q = topics.get(topic);
                if (q != null && !q.isEmpty()) return q.poll();
            }
            return null;
        }
    }
    public static void main(String[] args) {
        MessageQueue mq = new MessageQueue();
        mq.createTopic("orders"); mq.createTopic("payments");
        mq.subscribe("service-A", "orders"); mq.subscribe("service-B", "payments");
        mq.publish("orders", "Order #1"); mq.publish("orders", "Order #2"); mq.publish("payments", "Payment #1");
        Message m = mq.consume("service-A");
        System.out.println(m != null ? m.topic + ": " + m.payload : "empty"); // orders: Order #1
        m = mq.consume("service-B");
        System.out.println(m != null ? m.topic + ": " + m.payload : "empty"); // payments: Payment #1
    }
}
