/**
 * Problem 11: Search a 2D Matrix II
 * 
 * Matrix sorted row-wise and column-wise. Search for target.
 * 
 * Approach: Start from top-right corner. If current > target go left, else go down.
 * 
 * Time: O(m + n), Space: O(1)
 * 
 * Production Analogy: Navigating a multi-dimensional index (e.g., composite
 * index on two sorted dimensions) — eliminating rows/columns per step.
 */
public class Problem11_SearchA2DMatrixII {
    public static boolean searchMatrix(int[][] matrix, int target) {
        int row = 0, col = matrix[0].length - 1;
        while (row < matrix.length && col >= 0) {
            if (matrix[row][col] == target) return true;
            else if (matrix[row][col] > target) col--;
            else row++;
        }
        return false;
    }

    public static void main(String[] args) {
        int[][] m = {{1,4,7,11,15},{2,5,8,12,19},{3,6,9,16,22},{10,13,14,17,24},{18,21,23,26,30}};
        System.out.println(searchMatrix(m, 5));  // true
        System.out.println(searchMatrix(m, 20)); // false
        System.out.println(searchMatrix(new int[][]{{-5}}, -5)); // true
    }
}
