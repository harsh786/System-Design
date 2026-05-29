import java.util.*;

public class Problem48_RandomizedQueryStrategy {
    // Randomized strategy to find element with limited queries
    static int[] arr = {5,2,8,1,9,3,7,4,6,0};
    static int n = arr.length;
    
    static int query(int i) { return arr[i]; }
    
    // Find target with random sampling then binary search on candidates
    static int randomizedFind(int target, int sampleSize) {
        Random rand = new Random(42);
        // Random sample to narrow search
        int closest = -1, closestDiff = Integer.MAX_VALUE;
        for (int s = 0; s < sampleSize; s++) {
            int i = rand.nextInt(n);
            int v = query(i);
            if (v == target) return i;
            if (Math.abs(v - target) < closestDiff) { closestDiff = Math.abs(v - target); closest = i; }
        }
        // Linear scan as fallback
        for (int i = 0; i < n; i++) if (query(i) == target) return i;
        return -1;
    }
    
    public static void main(String[] args) {
        System.out.println("Find 7: index=" + randomizedFind(7, 3));
    }
}
