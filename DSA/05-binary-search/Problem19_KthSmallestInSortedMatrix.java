/**
 * Problem 19: Kth Smallest Element in a Sorted Matrix
 * 
 * n x n matrix sorted row-wise and column-wise. Find kth smallest.
 * 
 * Approach: Binary search on value range [matrix[0][0], matrix[n-1][n-1]].
 * Count elements <= mid using staircase traversal.
 * 
 * Time: O(n * log(max - min)), Space: O(1)
 * 
 * Production Analogy: Finding the kth percentile latency from a distributed
 * system where each node reports sorted latency buckets.
 */
public class Problem19_KthSmallestInSortedMatrix {
    public static int kthSmallest(int[][] matrix, int k) {
        int n = matrix.length;
        int lo = matrix[0][0], hi = matrix[n-1][n-1];
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (countLessOrEqual(matrix, mid) >= k) hi = mid;
            else lo = mid + 1;
        }
        return lo;
    }

    private static int countLessOrEqual(int[][] matrix, int target) {
        int n = matrix.length, count = 0;
        int row = n - 1, col = 0;
        while (row >= 0 && col < n) {
            if (matrix[row][col] <= target) { count += row + 1; col++; }
            else row--;
        }
        return count;
    }

    public static void main(String[] args) {
        int[][] m1 = {{1,5,9},{10,11,13},{12,13,15}};
        System.out.println(kthSmallest(m1, 8)); // 13
        System.out.println(kthSmallest(new int[][]{{-5}}, 1)); // -5
    }
}
