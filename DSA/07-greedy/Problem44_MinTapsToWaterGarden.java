/**
 * Problem 44: Minimum Number of Taps to Open to Water a Garden (LeetCode 1326)
 *
 * Greedy Choice: Convert to jump game - each tap covers a range. Find min jumps to cover [0, n].
 *
 * Time: O(n), Space: O(n)
 *
 * Production Analogy: Minimum CDN nodes to cover entire geographic range with overlap.
 */
public class Problem44_MinTapsToWaterGarden {
    
    public static int minTaps(int n, int[] ranges) {
        int[] maxReach = new int[n + 1];
        for (int i = 0; i <= n; i++) {
            int left = Math.max(0, i - ranges[i]);
            int right = Math.min(n, i + ranges[i]);
            maxReach[left] = Math.max(maxReach[left], right);
        }
        int taps = 0, curEnd = 0, farthest = 0;
        for (int i = 0; i <= n; i++) {
            if (i > farthest) return -1;
            if (i > curEnd) { taps++; curEnd = farthest; }
            farthest = Math.max(farthest, maxReach[i]);
        }
        return taps;
    }
    
    public static void main(String[] args) {
        System.out.println(minTaps(5, new int[]{3,4,1,1,0,0}));   // 1
        System.out.println(minTaps(3, new int[]{0,0,0,0}));        // -1
        System.out.println(minTaps(7, new int[]{1,2,1,0,2,1,0,1})); // 3
    }
}
