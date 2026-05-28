/**
 * Problem 10: Search a 2D Matrix
 * 
 * Matrix where each row is sorted and first element of each row > last of previous.
 * 
 * Approach: Treat as a flattened sorted array. Binary search with index mapping.
 * 
 * Time: O(log(m*n)), Space: O(1)
 * 
 * Production Analogy: Searching a partitioned sorted index across multiple
 * storage segments (like SSTable levels in LSM trees).
 */
public class Problem10_SearchA2DMatrix {
    public static boolean searchMatrix(int[][] matrix, int target) {
        int m = matrix.length, n = matrix[0].length;
        int lo = 0, hi = m * n - 1;
        while (lo <= hi) {
            int mid = lo + (hi - lo) / 2;
            int val = matrix[mid / n][mid % n];
            if (val == target) return true;
            else if (val < target) lo = mid + 1;
            else hi = mid - 1;
        }
        return false;
    }

    public static void main(String[] args) {
        int[][] m1 = {{1,3,5,7},{10,11,16,20},{23,30,34,60}};
        System.out.println(searchMatrix(m1, 3));  // true
        System.out.println(searchMatrix(m1, 13)); // false
        System.out.println(searchMatrix(new int[][]{{1}}, 1)); // true
        System.out.println(searchMatrix(new int[][]{{1}}, 2)); // false
    }
}
