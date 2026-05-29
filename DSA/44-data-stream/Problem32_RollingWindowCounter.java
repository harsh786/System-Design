import java.util.*;

public class Problem32_RollingWindowCounter {
    // Rolling Window Counter: Count events in last N seconds using bucketed approach.
    
    int[] buckets;
    int[] timestamps;
    int windowSize;
    int bucketCount;
    
    public Problem32_RollingWindowCounter() { init(60, 60); }
    
    public void init(int windowSeconds, int numBuckets) {
        this.windowSize = windowSeconds;
        this.bucketCount = numBuckets;
        buckets = new int[numBuckets];
        timestamps = new int[numBuckets];
    }
    
    public void increment(int timestamp) {
        int idx = timestamp % bucketCount;
        if (timestamps[idx] != timestamp) { timestamps[idx] = timestamp; buckets[idx] = 0; }
        buckets[idx]++;
    }
    
    public int count(int timestamp) {
        int total = 0;
        for (int i = 0; i < bucketCount; i++) {
            if (timestamp - timestamps[i] < windowSize) total += buckets[i];
        }
        return total;
    }
    
    public static void main(String[] args) {
        Problem32_RollingWindowCounter sol = new Problem32_RollingWindowCounter();
        sol.init(10, 10);
        sol.increment(1); sol.increment(1); sol.increment(5); sol.increment(9);
        System.out.println(sol.count(10)); // 4
        System.out.println(sol.count(11)); // 2 (time 1 expired)
    }
}
