import java.util.*;

public class Problem35_OnlinePercentileApproximation {
    // P2 Algorithm for online percentile approximation (simplified with sorted buffer).
    // For production, use t-digest or P2. Here: maintain sorted sample buffer.
    
    List<Double> buffer = new ArrayList<>();
    int maxSize;
    
    public Problem35_OnlinePercentileApproximation() { this.maxSize = 1000; }
    
    public void add(double value) {
        int pos = Collections.binarySearch(buffer, value);
        if (pos < 0) pos = -pos - 1;
        buffer.add(pos, value);
        // Downsample if too large (keep every other element)
        if (buffer.size() > maxSize * 2) {
            List<Double> newBuf = new ArrayList<>();
            for (int i = 0; i < buffer.size(); i += 2) newBuf.add(buffer.get(i));
            buffer = newBuf;
        }
    }
    
    public double percentile(double p) {
        if (buffer.isEmpty()) return 0;
        int idx = (int) Math.ceil(p / 100.0 * buffer.size()) - 1;
        idx = Math.max(0, Math.min(buffer.size() - 1, idx));
        return buffer.get(idx);
    }
    
    public static void main(String[] args) {
        Problem35_OnlinePercentileApproximation sol = new Problem35_OnlinePercentileApproximation();
        Random rand = new Random(42);
        for (int i = 0; i < 10000; i++) sol.add(rand.nextGaussian() * 10 + 50);
        System.out.printf("P50: %.2f, P90: %.2f, P99: %.2f%n",
            sol.percentile(50), sol.percentile(90), sol.percentile(99));
    }
}
