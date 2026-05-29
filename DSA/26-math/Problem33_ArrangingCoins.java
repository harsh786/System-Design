/**
 * Problem 33: Arranging Coins
 * Arrange n coins in staircase rows (row i has i coins). How many complete rows?
 *
 * Approach: Binary search or quadratic formula: k = floor((-1 + sqrt(1 + 8n)) / 2).
 * Time Complexity: O(1) with formula, O(log n) with binary search
 * Space Complexity: O(1)
 *
 * Production Analogy: Like determining how many complete batches fit in a
 * progressively-sized batch processing queue.
 */
public class Problem33_ArrangingCoins {

    public static int arrangeCoins(int n) {
        // k*(k+1)/2 <= n => k^2 + k - 2n <= 0
        return (int) ((-1 + Math.sqrt(1 + 8.0 * n)) / 2);
    }

    public static void main(String[] args) {
        System.out.println(arrangeCoins(5));           // 2
        System.out.println(arrangeCoins(8));           // 3
        System.out.println(arrangeCoins(1));           // 1
        System.out.println(arrangeCoins(Integer.MAX_VALUE)); // 65535
    }
}
