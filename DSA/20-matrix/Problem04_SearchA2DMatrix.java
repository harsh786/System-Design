import java.util.*;

/**
 * Problem 4: Search a 2D Matrix
 * 
 * Matrix where each row is sorted and first element of each row > last element of previous row.
 * Search for a target value.
 *
 * Approach: Treat as flattened sorted array, binary search with index mapping.
 * mid -> row = mid/cols, col = mid%cols
 *
 * Time Complexity: O(log(m*n))
 * Space Complexity: O(1)
 *
 * Production Analogy: Searching in a paginated sorted index (like B-tree leaf pages).
 * Each "row" is a page/block in storage, and binary search finds the right block then offset.
 */
public class Problem04_SearchA2DMatrix {

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
        int[][] m = {{1,3,5,7},{10,11,16,20},{23,30,34,60}};
        System.out.println("Test 1 (find 3): " + searchMatrix(m, 3));   // true
        System.out.println("Test 2 (find 13): " + searchMatrix(m, 13)); // false
        System.out.println("Test 3 (find 60): " + searchMatrix(m, 60)); // true
        System.out.println("Test 4 (find 1): " + searchMatrix(m, 1));   // true
        int[][] m2 = {{1}};
        System.out.println("Test 5 (single): " + searchMatrix(m2, 1));  // true
        System.out.println("Test 6 (single): " + searchMatrix(m2, 2));  // false
    }
}
