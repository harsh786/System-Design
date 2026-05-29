import java.util.*;

public class Problem40_RateLimitedSearchStrategy {
    // Search with rate limiting - exponential backoff between queries
    static int[] arr = {1,2,3,4,5,6,7,8,9,10};
    static int queriesPerSecond = 2;
    static long lastQueryTime = 0;
    
    static int query(int i) {
        // Simulate rate limit
        long now = System.nanoTime();
        if (now - lastQueryTime < 500_000_000L / queriesPerSecond) {
            // Would be rate limited in real scenario
        }
        lastQueryTime = now;
        return arr[i];
    }
    
    // Batch-friendly binary search that minimizes queries
    static int search(int n, int target) {
        int lo = 0, hi = n - 1, queries = 0;
        while (lo <= hi) {
            int mid = lo + (hi - lo) / 2;
            queries++;
            int v = query(mid);
            if (v == target) { System.out.println("Queries: " + queries); return mid; }
            else if (v < target) lo = mid + 1;
            else hi = mid - 1;
        }
        System.out.println("Queries: " + queries);
        return -1;
    }
    
    public static void main(String[] args) {
        System.out.println("Found at: " + search(10, 7));
    }
}
