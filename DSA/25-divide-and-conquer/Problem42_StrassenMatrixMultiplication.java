/**
 * Problem 42: Strassen Matrix Multiplication (Conceptual Implementation)
 * 
 * D&C Approach:
 * - DIVIDE: Split n×n matrices into four n/2 × n/2 submatrices
 * - CONQUER: Compute 7 products (instead of 8 in naive) using clever combinations:
 *   M1 = (A11+A22)(B11+B22), M2 = (A21+A22)B11, M3 = A11(B12-B22)
 *   M4 = A22(B21-B11), M5 = (A11+A12)B22, M6 = (A21-A11)(B11+B12)
 *   M7 = (A12-A22)(B21+B22)
 * - COMBINE: C11=M1+M4-M5+M7, C12=M3+M5, C21=M2+M4, C22=M1-M2+M3+M6
 * 
 * Recurrence: T(n) = 7T(n/2) + O(n^2)
 * Time: O(n^log2(7)) ≈ O(n^2.807) vs naive O(n^3)
 * Space: O(n^2 log n)
 * 
 * Production Analogy:
 * - Deep learning matrix operations (cuBLAS uses Strassen-like optimizations)
 * - Scientific computing (LAPACK)
 * - Not always practical due to constant factors; useful for very large matrices
 */
public class Problem42_StrassenMatrixMultiplication {

    private static final int THRESHOLD = 64; // Below this, use naive multiplication

    public static int[][] strassen(int[][] A, int[][] B) {
        int n = A.length;
        if (n <= THRESHOLD) return naiveMultiply(A, B);
        
        int half = n / 2;
        int[][] A11 = sub(A, 0, 0, half), A12 = sub(A, 0, half, half);
        int[][] A21 = sub(A, half, 0, half), A22 = sub(A, half, half, half);
        int[][] B11 = sub(B, 0, 0, half), B12 = sub(B, 0, half, half);
        int[][] B21 = sub(B, half, 0, half), B22 = sub(B, half, half, half);
        
        // 7 recursive multiplications
        int[][] M1 = strassen(add(A11, A22), add(B11, B22));
        int[][] M2 = strassen(add(A21, A22), B11);
        int[][] M3 = strassen(A11, subtract(B12, B22));
        int[][] M4 = strassen(A22, subtract(B21, B11));
        int[][] M5 = strassen(add(A11, A12), B22);
        int[][] M6 = strassen(subtract(A21, A11), add(B11, B12));
        int[][] M7 = strassen(subtract(A12, A22), add(B21, B22));
        
        // Combine
        int[][] C11 = add(subtract(add(M1, M4), M5), M7);
        int[][] C12 = add(M3, M5);
        int[][] C21 = add(M2, M4);
        int[][] C22 = add(subtract(add(M1, M3), M2), M6);
        
        return combine(C11, C12, C21, C22);
    }

    private static int[][] naiveMultiply(int[][] A, int[][] B) {
        int n = A.length;
        int[][] C = new int[n][n];
        for (int i = 0; i < n; i++)
            for (int j = 0; j < n; j++)
                for (int k = 0; k < n; k++)
                    C[i][j] += A[i][k] * B[k][j];
        return C;
    }

    private static int[][] sub(int[][] M, int r, int c, int size) {
        int[][] S = new int[size][size];
        for (int i = 0; i < size; i++)
            System.arraycopy(M[r + i], c, S[i], 0, size);
        return S;
    }

    private static int[][] add(int[][] A, int[][] B) {
        int n = A.length;
        int[][] C = new int[n][n];
        for (int i = 0; i < n; i++)
            for (int j = 0; j < n; j++) C[i][j] = A[i][j] + B[i][j];
        return C;
    }

    private static int[][] subtract(int[][] A, int[][] B) {
        int n = A.length;
        int[][] C = new int[n][n];
        for (int i = 0; i < n; i++)
            for (int j = 0; j < n; j++) C[i][j] = A[i][j] - B[i][j];
        return C;
    }

    private static int[][] combine(int[][] C11, int[][] C12, int[][] C21, int[][] C22) {
        int half = C11.length, n = half * 2;
        int[][] C = new int[n][n];
        for (int i = 0; i < half; i++) {
            System.arraycopy(C11[i], 0, C[i], 0, half);
            System.arraycopy(C12[i], 0, C[i], half, half);
            System.arraycopy(C21[i], 0, C[half + i], 0, half);
            System.arraycopy(C22[i], 0, C[half + i], half, half);
        }
        return C;
    }

    public static void main(String[] args) {
        int[][] A = {{1,2},{3,4}};
        int[][] B = {{5,6},{7,8}};
        int[][] C = strassen(A, B);
        // Expected: [[19,22],[43,50]]
        for (int[] row : C) System.out.println(java.util.Arrays.toString(row));
        
        System.out.println("---");
        int[][] A2 = {{1,0},{0,1}};
        int[][] C2 = strassen(A2, B);
        for (int[] row : C2) System.out.println(java.util.Arrays.toString(row));
    }
}
