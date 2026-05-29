import java.util.*;

/**
 * Problem 5: Search a 2D Matrix II
 * 
 * Matrix where rows and columns are sorted in ascending order. Search for target.
 *
 * Approach: Start from top-right corner. If current > target go left, else go down.
 * Each step eliminates a row or column.
 *
 * Time Complexity: O(m + n)
 * Space Complexity: O(1)
 *
 * Production Analogy: Searching in a 2D range-sorted index like a Young tableau.
 * Used in spatial databases where data is sorted on two dimensions independently.
 */
public class Problem05_SearchA2DMatrixII {

    public static boolean searchMatrix(int[][] matrix, int target) {
        int m = matrix.length, n = matrix[0].length;
        int i = 0, j = n - 1;
        while (i < m && j >= 0) {
            if (matrix[i][j] == target) return true;
            else if (matrix[i][j] > target) j--;
            else i++;
        }
        return false;
    }

    public static void main(String[] args) {
        int[][] m = {{1,4,7,11,15},{2,5,8,12,19},{3,6,9,16,22},{10,13,14,17,24},{18,21,23,26,30}};
        System.out.println("Test 1 (find 5): " + searchMatrix(m, 5));   // true
        System.out.println("Test 2 (find 20): " + searchMatrix(m, 20)); // false
        System.out.println("Test 3 (find 30): " + searchMatrix(m, 30)); // true
        System.out.println("Test 4 (find 1): " + searchMatrix(m, 1));   // true
    }
}
