import java.util.Arrays;

/**
 * Problem 32: Sparse Table Build
 * 
 * D&C / Doubling Approach:
 * - BUILD: For each power of 2 (length 1, 2, 4, 8...), compute min/max
 *   using results from previous power: table[i][j] = min(table[i][j-1], table[i+2^(j-1)][j-1])
 * - QUERY: Decompose range into two overlapping powers of 2
 * 
 * Time: Build O(n log n), Query O(1) for idempotent ops (min/max/gcd)
 * Space: O(n log n)
 * 
 * Production Analogy:
 * - Precomputed range-min for LCA (Lowest Common Ancestor) queries
 * - Fast range queries in competitive programming
 * - Static data analytics where queries vastly outnumber updates
 */
public class Problem32_SparseTableBuild {

    private int[][] sparse;
    private int[] log;

    public Problem32_SparseTableBuild(int[] arr) {
        int n = arr.length;
        int maxLog = (int) (Math.log(n) / Math.log(2)) + 1;
        sparse = new int[n][maxLog + 1];
        log = new int[n + 1];
        
        // Precompute logs
        for (int i = 2; i <= n; i++) log[i] = log[i / 2] + 1;
        
        // Base case: intervals of length 1
        for (int i = 0; i < n; i++) sparse[i][0] = arr[i];
        
        // Build: double the interval length each time
        for (int j = 1; j <= maxLog; j++) {
            for (int i = 0; i + (1 << j) - 1 < n; i++) {
                sparse[i][j] = Math.min(sparse[i][j - 1], sparse[i + (1 << (j - 1))][j - 1]);
            }
        }
    }

    // O(1) range minimum query
    public int query(int l, int r) {
        int k = log[r - l + 1];
        return Math.min(sparse[l][k], sparse[r - (1 << k) + 1][k]);
    }

    public static void main(String[] args) {
        Problem32_SparseTableBuild st = new Problem32_SparseTableBuild(new int[]{7, 2, 3, 0, 5, 10, 3, 12, 18});
        System.out.println(st.query(0, 4)); // 0
        System.out.println(st.query(4, 7)); // 3
        System.out.println(st.query(0, 8)); // 0
        System.out.println(st.query(0, 0)); // 7
        System.out.println(st.query(7, 8)); // 12
        System.out.println(st.query(1, 2)); // 2
    }
}
