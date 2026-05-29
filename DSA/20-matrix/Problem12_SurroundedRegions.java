import java.util.*;

/**
 * Problem 12: Surrounded Regions
 * 
 * Capture all 'O' regions surrounded by 'X'. Border-connected 'O's are not captured.
 *
 * Approach: DFS from border 'O's to mark safe cells, then flip remaining 'O' to 'X'.
 *
 * Time Complexity: O(m * n)
 * Space Complexity: O(m * n) recursion stack
 *
 * Production Analogy: In network security, identifying internal nodes not connected to
 * external gateway (border) - those can be safely isolated/firewalled.
 */
public class Problem12_SurroundedRegions {

    public static void solve(char[][] board) {
        int m = board.length, n = board[0].length;
        // Mark border-connected O's
        for (int i = 0; i < m; i++) { mark(board, i, 0); mark(board, i, n-1); }
        for (int j = 0; j < n; j++) { mark(board, 0, j); mark(board, m-1, j); }
        // Flip
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++) {
                if (board[i][j] == 'O') board[i][j] = 'X';
                if (board[i][j] == 'S') board[i][j] = 'O';
            }
    }

    private static void mark(char[][] board, int i, int j) {
        if (i < 0 || i >= board.length || j < 0 || j >= board[0].length || board[i][j] != 'O') return;
        board[i][j] = 'S';
        mark(board, i+1, j); mark(board, i-1, j); mark(board, i, j+1); mark(board, i, j-1);
    }

    public static void main(String[] args) {
        char[][] b = {{'X','X','X','X'},{'X','O','O','X'},{'X','X','O','X'},{'X','O','X','X'}};
        solve(b);
        System.out.println("Test 1: " + Arrays.deepToString(b));
        // [[X,X,X,X],[X,X,X,X],[X,X,X,X],[X,O,X,X]]

        char[][] b2 = {{'X'}};
        solve(b2);
        System.out.println("Test 2: " + Arrays.deepToString(b2));
    }
}
