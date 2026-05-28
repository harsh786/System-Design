import java.util.*;

/**
 * Problem 12: N-Queens II (LeetCode 52)
 * 
 * Return the number of distinct solutions to the n-queens puzzle.
 * 
 * Same as N-Queens but only count solutions instead of building board strings.
 * 
 * Time Complexity: O(n!)
 * Space Complexity: O(n)
 * 
 * Production Analogy:
 * - Counting valid configurations without materializing them (capacity planning).
 */
public class Problem12_NQueensII {

    private int count;

    public int totalNQueens(int n) {
        count = 0;
        backtrack(n, 0, new HashSet<>(), new HashSet<>(), new HashSet<>());
        return count;
    }

    private void backtrack(int n, int row, Set<Integer> cols, Set<Integer> diags, Set<Integer> antiDiags) {
        if (row == n) { count++; return; }
        for (int col = 0; col < n; col++) {
            int d = row - col, ad = row + col;
            if (cols.contains(col) || diags.contains(d) || antiDiags.contains(ad)) continue;
            cols.add(col); diags.add(d); antiDiags.add(ad);
            backtrack(n, row + 1, cols, diags, antiDiags);
            cols.remove(col); diags.remove(d); antiDiags.remove(ad);
        }
    }

    public static void main(String[] args) {
        Problem12_NQueensII sol = new Problem12_NQueensII();

        System.out.println("N=4: " + sol.totalNQueens(4)); // 2
        System.out.println("N=8: " + sol.totalNQueens(8)); // 92
        System.out.println("N=1: " + sol.totalNQueens(1)); // 1
        System.out.println("N=9: " + sol.totalNQueens(9)); // 352
    }
}
