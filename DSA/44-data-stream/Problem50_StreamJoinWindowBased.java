import java.util.*;

public class Problem50_StreamJoinWindowBased {
    // Window-based Stream Join: Join two streams within a time window.
    
    static class Event {
        String key;
        long timestamp;
        String value;
        Event(String k, long t, String v) { key = k; timestamp = t; value = v; }
    }
    
    long windowSize;
    // Buffer events from both streams keyed by join key
    Map<String, Deque<Event>> leftBuffer = new HashMap<>();
    Map<String, Deque<Event>> rightBuffer = new HashMap<>();
    
    public Problem50_StreamJoinWindowBased() { this.windowSize = 5000; }
    
    public void init(long windowSize) { this.windowSize = windowSize; }
    
    public List<String> addLeft(Event event) {
        cleanup(leftBuffer, event.timestamp);
        cleanup(rightBuffer, event.timestamp);
        leftBuffer.computeIfAbsent(event.key, k -> new ArrayDeque<>()).add(event);
        return matchWith(event, rightBuffer);
    }
    
    public List<String> addRight(Event event) {
        cleanup(leftBuffer, event.timestamp);
        cleanup(rightBuffer, event.timestamp);
        rightBuffer.computeIfAbsent(event.key, k -> new ArrayDeque<>()).add(event);
        return matchWith(event, leftBuffer);
    }
    
    private List<String> matchWith(Event event, Map<String, Deque<Event>> otherBuffer) {
        List<String> results = new ArrayList<>();
        Deque<Event> others = otherBuffer.getOrDefault(event.key, new ArrayDeque<>());
        for (Event o : others) {
            if (Math.abs(event.timestamp - o.timestamp) <= windowSize) {
                results.add("JOIN(" + event.key + "): " + o.value + " <-> " + event.value);
            }
        }
        return results;
    }
    
    private void cleanup(Map<String, Deque<Event>> buffer, long currentTime) {
        for (Deque<Event> dq : buffer.values()) {
            while (!dq.isEmpty() && currentTime - dq.peekFirst().timestamp > windowSize) dq.pollFirst();
        }
    }
    
    public static void main(String[] args) {
        Problem50_StreamJoinWindowBased sol = new Problem50_StreamJoinWindowBased();
        sol.init(3000);
        // Left stream: orders
        System.out.println(sol.addLeft(new Event("user1", 1000, "order1")));
        // Right stream: payments
        System.out.println(sol.addRight(new Event("user1", 2000, "pay1")));   // joins!
        System.out.println(sol.addRight(new Event("user1", 5000, "pay2")));   // still within window of order1? 5000-1000=4000>3000, no
        System.out.println(sol.addLeft(new Event("user1", 4500, "order2")));  // joins with pay2? 5000-4500=500<=3000, yes
        System.out.println(sol.addRight(new Event("user2", 6000, "pay3")));   // no match
    }
}
