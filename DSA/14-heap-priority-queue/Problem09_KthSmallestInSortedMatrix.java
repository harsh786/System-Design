import java.util.*;

/**
 * Problem 9: Kth Smallest Element in a Sorted Matrix (LeetCode 378)
 * 
 * Approach: Min-heap starting with first column, expand rightward.
 * 
 * Time Complexity: O(K log N) where N = matrix dimension
 * Space Complexity: O(N)
 * 
 * Production Analogy: Multi-way merge of sorted partitions in distributed databases
 * to find the Kth record in global sort order.
 */
public class Problem09_KthSmallestInSortedMatrix {
    
    public int kthSmallest(int[][] matrix, int k) {
        int n = matrix.length;
        PriorityQueue<int[]> minHeap = new PriorityQueue<>((a, b) -> a[0] - b[0]);
        for (int i = 0; i < n; i++) minHeap.offer(new int[]{matrix[i][0], i, 0});
        
        int result = 0;
        while (k-- > 0) {
            int[] curr = minHeap.poll();
            result = curr[0];
            int row = curr[1], col = curr[2];
            if (col + 1 < n) minHeap.offer(new int[]{matrix[row][col + 1], row, col + 1});
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem09_KthSmallestInSortedMatrix sol = new Problem09_KthSmallestInSortedMatrix();
        System.out.println(sol.kthSmallest(new int[][]{{1,5,9},{10,11,13},{12,13,15}}, 8)); // 13
        System.out.println(sol.kthSmallest(new int[][]{{-5}}, 1)); // -5
    }
}
