import java.util.*;

public class Problem41_LossyCounting {
    // Lossy Counting: Find frequent items in stream with error bound epsilon.
    // Item with true freq >= s*N will be output (with possible false positives up to (s-epsilon)*N).
    
    Map<Integer, int[]> counters = new HashMap<>(); // item -> [count, delta]
    int bucketWidth;
    int currentBucket = 1;
    int itemCount = 0;
    
    public Problem41_LossyCounting() { init(0.01); }
    
    public void init(double epsilon) { this.bucketWidth = (int) Math.ceil(1.0 / epsilon); }
    
    public void add(int item) {
        itemCount++;
        if (counters.containsKey(item)) { counters.get(item)[0]++; }
        else counters.put(item, new int[]{1, currentBucket - 1});
        
        if (itemCount % bucketWidth == 0) {
            // Prune
            counters.entrySet().removeIf(e -> e.getValue()[0] + e.getValue()[1] <= currentBucket);
            currentBucket++;
        }
    }
    
    public List<Integer> getFrequent(double support) {
        List<Integer> result = new ArrayList<>();
        int threshold = (int)(support * itemCount - bucketWidth);
        for (var e : counters.entrySet()) {
            if (e.getValue()[0] >= threshold) result.add(e.getKey());
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem41_LossyCounting sol = new Problem41_LossyCounting();
        sol.init(0.1);
        Random rand = new Random(0);
        for (int i = 0; i < 10000; i++) {
            if (rand.nextDouble() < 0.3) sol.add(1);
            else if (rand.nextDouble() < 0.5) sol.add(2);
            else sol.add(rand.nextInt(100) + 3);
        }
        System.out.println("Frequent items (support=0.1): " + sol.getFrequent(0.1));
    }
}
