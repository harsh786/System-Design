/**
 * Problem 45: Maximum Candies Allocated to K Children
 * 
 * Piles of candies. Give each of k children same amount. Maximize per-child amount.
 * 
 * Approach: Binary search on answer [1, max]. Count piles/mid >= k.
 * 
 * Time: O(n * log(max)), Space: O(1)
 * 
 * Production Analogy: Maximum equal bandwidth allocation per tenant from
 * shared network capacity pools.
 */
public class Problem45_MaximumCandiesAllocated {
    public static int maximumCandies(int[] candies, long k) {
        int lo = 1, hi = 0;
        for (int c : candies) hi = Math.max(hi, c);
        if (hi == 0) return 0;
        
        int ans = 0;
        while (lo <= hi) {
            int mid = lo + (hi - lo) / 2;
            long count = 0;
            for (int c : candies) count += c / mid;
            if (count >= k) { ans = mid; lo = mid + 1; }
            else hi = mid - 1;
        }
        return ans;
    }

    public static void main(String[] args) {
        System.out.println(maximumCandies(new int[]{5,8,6}, 3));   // 5
        System.out.println(maximumCandies(new int[]{2,5}, 11));    // 0
        System.out.println(maximumCandies(new int[]{4,7,5}, 4));   // 3
    }
}
