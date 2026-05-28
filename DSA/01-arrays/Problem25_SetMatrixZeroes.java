import java.util.*;

/**
 * Problem 25: Set Matrix Zeroes
 * If element is 0, set its entire row and column to 0.
 * 
 * Production Analogy: Like cascading failure propagation - one failed node (0)
 * takes down its entire row (horizontal dependencies) and column (vertical dependencies).
 * 
 * O(m*n) time, O(1) space - use first row/col as markers
 */
public class Problem25_SetMatrixZeroes {

    public static void setZeroes(int[][] matrix) {
        int m = matrix.length, n = matrix[0].length;
        boolean firstRowZero = false, firstColZero = false;
        for (int i = 0; i < m; i++) if (matrix[i][0] == 0) firstColZero = true;
        for (int j = 0; j < n; j++) if (matrix[0][j] == 0) firstRowZero = true;
        for (int i = 1; i < m; i++)
            for (int j = 1; j < n; j++)
                if (matrix[i][j] == 0) { matrix[i][0] = 0; matrix[0][j] = 0; }
        for (int i = 1; i < m; i++)
            for (int j = 1; j < n; j++)
                if (matrix[i][0] == 0 || matrix[0][j] == 0) matrix[i][j] = 0;
        if (firstColZero) for (int i = 0; i < m; i++) matrix[i][0] = 0;
        if (firstRowZero) for (int j = 0; j < n; j++) matrix[0][j] = 0;
    }

    public static void main(String[] args) {
        int[][] m1 = {{1,1,1},{1,0,1},{1,1,1}};
        setZeroes(m1);
        System.out.println(Arrays.deepToString(m1)); // [[1,0,1],[0,0,0],[1,0,1]]
        int[][] m2 = {{0,1,2,0},{3,4,5,2},{1,3,1,5}};
        setZeroes(m2);
        System.out.println(Arrays.deepToString(m2)); // [[0,0,0,0],[0,4,5,0],[0,3,1,0]]
    }
}
