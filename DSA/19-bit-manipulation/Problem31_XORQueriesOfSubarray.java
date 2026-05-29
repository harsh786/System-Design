/**
 * Problem 31: XOR Queries of a Subarray
 * Answer queries [l, r] with XOR of arr[l..r].
 * 
 * Approach: Prefix XOR. xor(l,r) = prefix[r+1] ^ prefix[l].
 * Time: O(n + q), Space: O(n)
 * 
 * Production Analogy: Precomputed checksums for efficient range integrity verification.
 */
public class Problem31_XORQueriesOfSubarray {
    public static int[] xorQueries(int[] arr, int[][] queries) {
        int n = arr.length;
        int[] prefix = new int[n + 1];
        for (int i = 0; i < n; i++) prefix[i + 1] = prefix[i] ^ arr[i];
        int[] result = new int[queries.length];
        for (int i = 0; i < queries.length; i++) {
            result[i] = prefix[queries[i][1] + 1] ^ prefix[queries[i][0]];
        }
        return result;
    }

    public static void main(String[] args) {
        int[] r = xorQueries(new int[]{1,3,4,8}, new int[][]{{0,1},{1,2},{0,3},{3,3}});
        for (int v : r) System.out.print(v + " "); // 2 7 14 8
        System.out.println();
    }
}
