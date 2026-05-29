import java.util.*;

/**
 * Problem 19: Kth Smallest Element in a Sorted Matrix
 * 
 * Matrix where rows and columns are sorted. Find kth smallest element.
 *
 * Approach: Binary search on value range. Count elements <= mid in O(m+n) using
 * staircase traversal from bottom-left.
 *
 * Time Complexity: O((m+n) * log(max-min))
 * Space Complexity: O(1)
 *
 * Production Analogy: Finding percentile values in a distributed sorted dataset
 * without materializing all data - like finding P99 latency across sharded metrics.
 */
public class Problem19_KthSmallestInSortedMatrix {

    public static int kthSmallest(int[][] matrix, int k) {
        int n = matrix.length;
        int lo = matrix[0][0], hi = matrix[n-1][n-1];
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (countLessEqual(matrix, mid) < k) lo = mid + 1;
            else hi = mid;
        }
        return lo;
    }

    private static int countLessEqual(int[][] matrix, int target) {
        int n = matrix.length, count = 0, j = n - 1;
        for (int i = 0; i < n; i++) {
            while (j >= 0 && matrix[i][j] > target) j--;
            count += j + 1;
        }
        return count;
    }

    public static void main(String[] args) {
        int[][] m = {{1,5,9},{10,11,13},{12,13,15}};
        System.out.println("Test 1 (k=8): " + kthSmallest(m, 8)); // 13
        System.out.println("Test 2 (k=1): " + kthSmallest(m, 1)); // 1
        System.out.println("Test 3: " + kthSmallest(new int[][]{{-5}}, 1)); // -5
    }
}
