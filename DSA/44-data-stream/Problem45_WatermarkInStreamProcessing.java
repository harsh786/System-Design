import java.util.*;

public class Problem45_WatermarkInStreamProcessing {
    // Watermark: Tracks progress of event time. Events before watermark are considered complete.
    
    long watermark = Long.MIN_VALUE;
    long maxLateness;
    TreeMap<Long, List<String>> pendingWindows = new TreeMap<>();
    
    public Problem45_WatermarkInStreamProcessing() { this.maxLateness = 3000; }
    
    public void init(long maxLateness) { this.maxLateness = maxLateness; }
    
    public List<String> onEvent(long eventTime, String data) {
        // Update watermark
        watermark = Math.max(watermark, eventTime - maxLateness);
        
        // Buffer in window
        long windowKey = eventTime / 5000 * 5000; // 5-second tumbling window
        pendingWindows.computeIfAbsent(windowKey, k -> new ArrayList<>()).add(data);
        
        // Emit completed windows
        List<String> emitted = new ArrayList<>();
        while (!pendingWindows.isEmpty() && pendingWindows.firstKey() + 5000 <= watermark) {
            Map.Entry<Long, List<String>> entry = pendingWindows.pollFirstEntry();
            emitted.add("Window[" + entry.getKey() + "]: " + entry.getValue());
        }
        return emitted;
    }
    
    public static void main(String[] args) {
        Problem45_WatermarkInStreamProcessing sol = new Problem45_WatermarkInStreamProcessing();
        sol.init(2000);
        String[][] events = {{"1000","a"},{"2000","b"},{"6000","c"},{"9000","d"},{"15000","e"}};
        for (String[] e : events) {
            List<String> out = sol.onEvent(Long.parseLong(e[0]), e[1]);
            if (!out.isEmpty()) System.out.println("Emitted: " + out);
        }
    }
}
