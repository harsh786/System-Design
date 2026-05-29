import java.util.*;

public class Problem48_TumblingWindowCounter {
    // Tumbling Window: Fixed-size, non-overlapping time windows.
    
    long windowSize;
    Map<Long, Integer> windows = new HashMap<>();
    
    public Problem48_TumblingWindowCounter() { this.windowSize = 5000; }
    
    public void init(long windowSize) { this.windowSize = windowSize; }
    
    public void addEvent(long timestamp) {
        long windowId = timestamp / windowSize;
        windows.merge(windowId, 1, Integer::sum);
    }
    
    public int getWindowCount(long timestamp) {
        long windowId = timestamp / windowSize;
        return windows.getOrDefault(windowId, 0);
    }
    
    public Map<Long, Integer> getAllWindows() { return windows; }
    
    public static void main(String[] args) {
        Problem48_TumblingWindowCounter sol = new Problem48_TumblingWindowCounter();
        sol.init(5000);
        long[] events = {1000, 2000, 3000, 6000, 7000, 11000, 12000, 13000, 14000};
        for (long t : events) sol.addEvent(t);
        System.out.println("Window at 1000: " + sol.getWindowCount(1000));  // 3
        System.out.println("Window at 6000: " + sol.getWindowCount(6000));  // 2
        System.out.println("Window at 11000: " + sol.getWindowCount(11000)); // 4
    }
}
