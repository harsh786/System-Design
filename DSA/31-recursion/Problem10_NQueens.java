import java.util.*;

public class Problem10_NQueens {
    public static List<List<String>> solveNQueens(int n) {
        List<List<String>> res = new ArrayList<>();
        char[][] board = new char[n][n];
        for (char[] row : board) Arrays.fill(row, '.');
        solve(res, board, 0, n);
        return res;
    }
    static void solve(List<List<String>> res, char[][] board, int row, int n) {
        if (row == n) { List<String> r = new ArrayList<>(); for (char[] rw : board) r.add(new String(rw)); res.add(r); return; }
        for (int col = 0; col < n; col++) {
            if (isValid(board, row, col, n)) { board[row][col] = 'Q'; solve(res, board, row + 1, n); board[row][col] = '.'; }
        }
    }
    static boolean isValid(char[][] board, int row, int col, int n) {
        for (int i = 0; i < row; i++) if (board[i][col] == 'Q') return false;
        for (int i = row-1, j = col-1; i >= 0 && j >= 0; i--, j--) if (board[i][j] == 'Q') return false;
        for (int i = row-1, j = col+1; i >= 0 && j < n; i--, j++) if (board[i][j] == 'Q') return false;
        return true;
    }
    public static void main(String[] args) {
        System.out.println(solveNQueens(4).size()); // 2
    }
}
