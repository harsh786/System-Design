/**
 * Problem 44: N-Queens (Bitmask approach)
 * 
 * Approach: Use 3 bitmasks: columns, left diagonals, right diagonals.
 * Available positions = ~(cols | diag1 | diag2) & ((1<<n)-1).
 * Time: O(n!), Space: O(n)
 * 
 * Production Analogy: Non-conflicting resource scheduling across multiple constraint dimensions.
 */
import java.util.*;

public class Problem44_NQueens {
    static int count;

    public static int totalNQueens(int n) {
        count = 0;
        solve(n, 0, 0, 0, 0);
        return count;
    }

    private static void solve(int n, int row, int cols, int diag1, int diag2) {
        if (row == n) { count++; return; }
        int available = ~(cols | diag1 | diag2) & ((1 << n) - 1);
        while (available != 0) {
            int pos = available & (-available); // lowest set bit
            available &= (available - 1);
            solve(n, row + 1, cols | pos, (diag1 | pos) << 1, (diag2 | pos) >> 1);
        }
    }

    public static void main(String[] args) {
        System.out.println(totalNQueens(4)); // 2
        System.out.println(totalNQueens(8)); // 92
        System.out.println(totalNQueens(1)); // 1
    }
}
