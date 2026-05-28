import java.util.*;

/**
 * Problem 11: N-Queens (LeetCode 51)
 * 
 * Place n queens on an n×n chessboard such that no two queens attack each other.
 * 
 * Search Tree:
 * - Place one queen per row. At row r, try columns 0..n-1.
 * - Check column conflicts, diagonal conflicts.
 * 
 * Pruning Strategy:
 * - Use sets for columns, diagonals (row-col), anti-diagonals (row+col)
 * - Skip any column that conflicts with existing queens
 * 
 * Time Complexity: O(n!) approximately
 * Space Complexity: O(n^2) for board + O(n) for tracking sets
 * 
 * Production Analogy:
 * - Resource placement with constraints: placing n services on n nodes where certain
 *   co-locations are forbidden (e.g., anti-affinity rules in Kubernetes).
 */
public class Problem11_NQueens {

    public List<List<String>> solveNQueens(int n) {
        List<List<String>> result = new ArrayList<>();
        char[][] board = new char[n][n];
        for (char[] row : board) Arrays.fill(row, '.');
        backtrack(board, 0, new HashSet<>(), new HashSet<>(), new HashSet<>(), result);
        return result;
    }

    private void backtrack(char[][] board, int row, Set<Integer> cols, Set<Integer> diags, Set<Integer> antiDiags, List<List<String>> result) {
        int n = board.length;
        if (row == n) {
            List<String> snapshot = new ArrayList<>();
            for (char[] r : board) snapshot.add(new String(r));
            result.add(snapshot);
            return;
        }
        for (int col = 0; col < n; col++) {
            int diag = row - col, antiDiag = row + col;
            if (cols.contains(col) || diags.contains(diag) || antiDiags.contains(antiDiag)) continue;
            board[row][col] = 'Q';
            cols.add(col); diags.add(diag); antiDiags.add(antiDiag);
            backtrack(board, row + 1, cols, diags, antiDiags, result);
            board[row][col] = '.';
            cols.remove(col); diags.remove(diag); antiDiags.remove(antiDiag);
        }
    }

    public static void main(String[] args) {
        Problem11_NQueens sol = new Problem11_NQueens();

        System.out.println("N=4: " + sol.solveNQueens(4).size() + " solutions");
        System.out.println(sol.solveNQueens(4));
        System.out.println("N=1: " + sol.solveNQueens(1));
        System.out.println("N=8: " + sol.solveNQueens(8).size() + " solutions");
    }
}
