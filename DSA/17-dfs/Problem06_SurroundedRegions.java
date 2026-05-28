import java.util.*;

/**
 * Problem: Surrounded Regions (LeetCode 130)
 * Approach: DFS from borders - mark border-connected 'O's, then flip remaining
 * Time: O(M*N), Space: O(M*N)
 * Production Analogy: Identifying internal-only services not exposed to external traffic
 */
public class Problem06_SurroundedRegions {
    public void solve(char[][] board) {
        int m = board.length, n = board[0].length;
        for (int i = 0; i < m; i++) { mark(board, i, 0); mark(board, i, n-1); }
        for (int j = 0; j < n; j++) { mark(board, 0, j); mark(board, m-1, j); }
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++) {
                if (board[i][j] == 'O') board[i][j] = 'X';
                else if (board[i][j] == 'S') board[i][j] = 'O';
            }
    }

    private void mark(char[][] board, int i, int j) {
        if (i < 0 || i >= board.length || j < 0 || j >= board[0].length || board[i][j] != 'O') return;
        board[i][j] = 'S';
        mark(board, i+1, j); mark(board, i-1, j); mark(board, i, j+1); mark(board, i, j-1);
    }

    public static void main(String[] args) {
        char[][] board = {{'X','X','X','X'},{'X','O','O','X'},{'X','X','O','X'},{'X','O','X','X'}};
        new Problem06_SurroundedRegions().solve(board);
        for (char[] row : board) System.out.println(Arrays.toString(row));
    }
}
