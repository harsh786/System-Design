/**
 * Problem 5: Search a 2D Matrix II (LeetCode 240)
 * 
 * D&C Approach:
 * - DIVIDE: Start from top-right (or bottom-left) corner
 * - Each comparison eliminates a row or column (like binary search in 2D)
 * - Alternative D&C: divide matrix into 4 quadrants, prune impossible quadrants
 * 
 * Time: O(m + n) for staircase approach, O(n*m^(log2(3))) for quadrant D&C
 * Space: O(1) for staircase, O(log(mn)) for recursive quadrant approach
 * 
 * Production Analogy:
 * - Searching sorted index partitions in columnar databases
 * - Range queries in 2D spatial indexes (R-trees prune quadrants similarly)
 */
public class Problem05_Search2DMatrixII {

    // Staircase search - elegant D&C eliminating row/col each step
    public static boolean searchMatrix(int[][] matrix, int target) {
        if (matrix == null || matrix.length == 0) return false;
        int row = 0, col = matrix[0].length - 1;
        while (row < matrix.length && col >= 0) {
            if (matrix[row][col] == target) return true;
            else if (matrix[row][col] > target) col--; // Eliminate column
            else row++; // Eliminate row
        }
        return false;
    }

    // Pure D&C approach - divide into quadrants
    public static boolean searchMatrixDC(int[][] matrix, int target) {
        if (matrix == null || matrix.length == 0) return false;
        return search(matrix, target, 0, 0, matrix.length - 1, matrix[0].length - 1);
    }

    private static boolean search(int[][] m, int target, int r1, int c1, int r2, int c2) {
        if (r1 > r2 || c1 > c2) return false;
        if (target < m[r1][c1] || target > m[r2][c2]) return false;
        int midCol = (c1 + c2) / 2;
        int row = r1;
        while (row <= r2 && m[row][midCol] <= target) {
            if (m[row][midCol] == target) return true;
            row++;
        }
        // Search bottom-left and top-right quadrants
        return search(m, target, row, c1, r2, midCol - 1) ||
               search(m, target, r1, midCol + 1, row - 1, c2);
    }

    public static void main(String[] args) {
        int[][] matrix = {
            {1,4,7,11,15},
            {2,5,8,12,19},
            {3,6,9,16,22},
            {10,13,14,17,24},
            {18,21,23,26,30}
        };
        System.out.println(searchMatrix(matrix, 5));  // true
        System.out.println(searchMatrix(matrix, 20)); // false
        System.out.println(searchMatrixDC(matrix, 14)); // true
        System.out.println(searchMatrixDC(matrix, 25)); // false
        System.out.println(searchMatrix(new int[][]{{1}}, 1)); // true
    }
}
