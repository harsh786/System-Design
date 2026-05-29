import java.util.*;

public class Problem49_HoppingWindowAggregation {
    // Hopping (Sliding) Window: Windows of size W, advancing by hop H (W > H means overlap).
    
    long windowSize;
    long hopSize;
    Map<Long, Integer> windowCounts = new TreeMap<>();
    
    public Problem49_HoppingWindowAggregation() { this.windowSize = 10000; this.hopSize = 5000; }
    
    public void init(long windowSize, long hopSize) { this.windowSize = windowSize; this.hopSize = hopSize; }
    
    public void addEvent(long timestamp, int value) {
        // Event belongs to all windows where windowStart <= timestamp < windowStart + windowSize
        // Window starts are multiples of hopSize
        long firstWindow = (timestamp / hopSize) * hopSize - windowSize + hopSize;
        for (long start = Math.max(0, firstWindow); start <= timestamp; start += hopSize) {
            if (timestamp < start + windowSize) {
                windowCounts.merge(start, value, Integer::sum);
            }
        }
    }
    
    public int getWindow(long windowStart) { return windowCounts.getOrDefault(windowStart, 0); }
    
    public static void main(String[] args) {
        Problem49_HoppingWindowAggregation sol = new Problem49_HoppingWindowAggregation();
        sol.init(10, 5); // window=10, hop=5
        sol.addEvent(1, 1); sol.addEvent(3, 1); sol.addEvent(7, 1); sol.addEvent(12, 1);
        System.out.println("All windows: " + sol.windowCounts);
    }
}
