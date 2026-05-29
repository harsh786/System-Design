/**
 * Problem 37: Optimal Binary Search Tree
 * Given keys with search frequencies, build BST minimizing expected search cost.
 * 
 * D&C Approach:
 * - DIVIDE: Choose each key k as root, splitting keys into left/right subtrees
 * - CONQUER: Recursively find optimal BST for keys < k and keys > k
 * - COMBINE: Cost = left_cost + right_cost + sum(frequencies in subtree)
 *   (because all nodes go one level deeper when under a root)
 * 
 * Time: O(n^3), Space: O(n^2)
 * 
 * Production Analogy:
 * - Huffman-like encoding trees for variable-frequency lookups
 * - Database index organization based on query frequency
 * - Optimizing search trie structure for common queries
 */
public class Problem37_OptimalBinarySearchTree {

    public static int optimalBST(int[] keys, int[] freq) {
        int n = keys.length;
        int[][] dp = new int[n][n];
        
        // Base case: single keys
        for (int i = 0; i < n; i++) dp[i][i] = freq[i];
        
        // Fill for increasing lengths
        for (int len = 2; len <= n; len++) {
            for (int i = 0; i <= n - len; i++) {
                int j = i + len - 1;
                dp[i][j] = Integer.MAX_VALUE;
                int freqSum = 0;
                for (int f = i; f <= j; f++) freqSum += freq[f];
                
                for (int r = i; r <= j; r++) {
                    int left = (r > i) ? dp[i][r - 1] : 0;
                    int right = (r < j) ? dp[r + 1][j] : 0;
                    int cost = left + right + freqSum;
                    dp[i][j] = Math.min(dp[i][j], cost);
                }
            }
        }
        return dp[0][n - 1];
    }

    public static void main(String[] args) {
        System.out.println(optimalBST(new int[]{10, 12, 20}, new int[]{34, 8, 50})); // 142
        System.out.println(optimalBST(new int[]{10, 20, 30, 40}, new int[]{4, 2, 6, 3})); // 26
        System.out.println(optimalBST(new int[]{1}, new int[]{5})); // 5
        System.out.println(optimalBST(new int[]{1, 2}, new int[]{1, 10})); // 12
    }
}
