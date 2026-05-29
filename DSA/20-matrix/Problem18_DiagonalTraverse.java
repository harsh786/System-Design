import java.util.*;

/**
 * Problem 18: Diagonal Traverse
 * 
 * Traverse matrix in diagonal zigzag order.
 *
 * Approach: Track direction (up-right or down-left). Handle boundary transitions.
 *
 * Time Complexity: O(m * n)
 * Space Complexity: O(1) extra
 *
 * Production Analogy: JPEG encoding uses zigzag traversal of DCT coefficient matrices
 * to group low-frequency components together for better compression.
 */
public class Problem18_DiagonalTraverse {

    public static int[] findDiagonalOrder(int[][] mat) {
        int m = mat.length, n = mat[0].length;
        int[] result = new int[m * n];
        int r = 0, c = 0, d = 1; // d=1 going up, d=-1 going down
        for (int i = 0; i < m * n; i++) {
            result[i] = mat[r][c];
            if (d == 1) { // going up-right
                if (c == n-1) { r++; d = -1; }
                else if (r == 0) { c++; d = -1; }
                else { r--; c++; }
            } else { // going down-left
                if (r == m-1) { c++; d = 1; }
                else if (c == 0) { r++; d = 1; }
                else { r++; c--; }
            }
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println("Test 1: " + Arrays.toString(findDiagonalOrder(new int[][]{{1,2,3},{4,5,6},{7,8,9}})));
        // [1,2,4,7,5,3,6,8,9] -- wait, should be [1,2,4,7,5,3,6,8,9]
        System.out.println("Test 2: " + Arrays.toString(findDiagonalOrder(new int[][]{{1,2},{3,4}})));
    }
}
