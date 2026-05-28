/**
 * Problem 30: Arranging Coins
 * 
 * Given n coins, build staircase rows (row i has i coins). Return complete rows.
 * 
 * Approach: Binary search for largest k where k*(k+1)/2 <= n.
 * 
 * Time: O(log n), Space: O(1)
 * 
 * Production Analogy: Determining how many complete batches of increasing
 * size can be served from a fixed resource pool.
 */
public class Problem30_ArrangingCoins {
    public static int arrangeCoins(int n) {
        long lo = 1, hi = n;
        while (lo <= hi) {
            long mid = lo + (hi - lo) / 2;
            long used = mid * (mid + 1) / 2;
            if (used == n) return (int) mid;
            else if (used < n) lo = mid + 1;
            else hi = mid - 1;
        }
        return (int) hi;
    }

    public static void main(String[] args) {
        System.out.println(arrangeCoins(5));  // 2
        System.out.println(arrangeCoins(8));  // 3
        System.out.println(arrangeCoins(1));  // 1
        System.out.println(arrangeCoins(2147483647)); // 65535
    }
}
