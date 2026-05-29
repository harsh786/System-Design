import java.util.*;

public class Problem44_EventTimeVsProcessingTime {
    // Event Time vs Processing Time: Handle out-of-order events in a stream.
    // Buffer events and process by event time, not arrival time.
    
    static class Event implements Comparable<Event> {
        long eventTime;
        long processingTime;
        String data;
        Event(long et, long pt, String d) { eventTime = et; processingTime = pt; data = d; }
        public int compareTo(Event o) { return Long.compare(eventTime, o.eventTime); }
    }
    
    PriorityQueue<Event> buffer = new PriorityQueue<>();
    long watermark = 0;
    
    public List<Event> processEvent(Event event) {
        buffer.offer(event);
        // Advance watermark (simplified: max event time - allowed lateness)
        watermark = Math.max(watermark, event.eventTime - 5000); // 5s allowed lateness
        
        List<Event> ready = new ArrayList<>();
        while (!buffer.isEmpty() && buffer.peek().eventTime <= watermark) {
            ready.add(buffer.poll());
        }
        return ready;
    }
    
    public static void main(String[] args) {
        Problem44_EventTimeVsProcessingTime sol = new Problem44_EventTimeVsProcessingTime();
        // Events arrive out of order
        Event e1 = new Event(1000, 1000, "A");
        Event e2 = new Event(3000, 2000, "B"); // arrives early
        Event e3 = new Event(2000, 3000, "C"); // late arrival
        Event e4 = new Event(8000, 4000, "D"); // triggers watermark
        
        for (Event e : new Event[]{e1, e2, e3, e4}) {
            List<Event> ready = sol.processEvent(e);
            if (!ready.isEmpty()) {
                System.out.print("Emitting: ");
                for (Event r : ready) System.out.print(r.data + "(t=" + r.eventTime + ") ");
                System.out.println();
            }
        }
    }
}
