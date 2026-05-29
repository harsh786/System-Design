/**
 * Problem 41: 2D Difference Matrix
 * 
 * Pattern: 2D difference array for range updates on a matrix.
 * For update (r1,c1,r2,c2,val):
 *   diff[r1][c1] += val; diff[r1][c2+1] -= val;
 *   diff[r2+1][c1] -= val; diff[r2+1][c2+1] += val;
 * Then 2D prefix sum to reconstruct.
 * 
 * Time: O(m*n + k) for k updates, Space: O(m*n)
 * 
 * Production Analogy: Applying batch regional pricing adjustments across a
 * geographic grid without iterating each cell individually.
 */
import java.util.Arrays;

public class Problem41_2DDifferenceMatrix {

    public static int[][] apply2DRangeUpdates(int m, int n, int[][] updates) {
        int[][] diff = new int[m + 1][n + 1];
        for (int[] u : updates) {
            int r1 = u[0], c1 = u[1], r2 = u[2], c2 = u[3], val = u[4];
            diff[r1][c1] += val;
            diff[r1][c2 + 1] -= val;
            diff[r2 + 1][c1] -= val;
            diff[r2 + 1][c2 + 1] += val;
        }
        // 2D prefix sum
        int[][] result = new int[m][n];
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++) {
                diff[i][j] += (i > 0 ? diff[i - 1][j] : 0) + (j > 0 ? diff[i][j - 1] : 0)
                             - (i > 0 && j > 0 ? diff[i - 1][j - 1] : 0);
                result[i][j] = diff[i][j];
            }
        return result;
    }

    public static void main(String[] args) {
        int[][] updates = {{0, 0, 1, 1, 2}, {1, 1, 2, 2, 3}};
        int[][] r = apply2DRangeUpdates(3, 3, updates);
        assert r[0][0] == 2 && r[0][1] == 2 && r[0][2] == 0;
        assert r[1][0] == 2 && r[1][1] == 5 && r[1][2] == 3;
        assert r[2][0] == 0 && r[2][1] == 3 && r[2][2] == 3;
        System.out.println("All tests passed!");
    }
}
