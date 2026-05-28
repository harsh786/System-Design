import java.util.Arrays;

/**
 * Problem 22: Aggressive Cows
 * 
 * Place k cows in stalls to maximize minimum distance between any two cows.
 * 
 * Approach: Binary search on answer [1, max-min]. Check if we can place k cows
 * with at least 'mid' distance apart greedily.
 * 
 * Time: O(n log n + n * log(range)), Space: O(1)
 * 
 * Production Analogy: Placing replicas across data centers to maximize minimum
 * geographic distance for fault tolerance.
 */
public class Problem22_AggressiveCows {
    public static int aggressiveCows(int[] stalls, int k) {
        Arrays.sort(stalls);
        int lo = 1, hi = stalls[stalls.length - 1] - stalls[0];
        
        while (lo < hi) {
            int mid = lo + (hi - lo + 1) / 2; // upper mid to avoid infinite loop
            if (canPlace(stalls, mid, k)) lo = mid;
            else hi = mid - 1;
        }
        return lo;
    }

    private static boolean canPlace(int[] stalls, int minDist, int k) {
        int count = 1, lastPos = stalls[0];
        for (int i = 1; i < stalls.length; i++) {
            if (stalls[i] - lastPos >= minDist) { count++; lastPos = stalls[i]; }
        }
        return count >= k;
    }

    public static void main(String[] args) {
        System.out.println(aggressiveCows(new int[]{1,2,4,8,9}, 3)); // 3
        System.out.println(aggressiveCows(new int[]{1,2,8,4,9}, 3)); // 3
        System.out.println(aggressiveCows(new int[]{0,3,4,7,10,9}, 4)); // 3
    }
}
