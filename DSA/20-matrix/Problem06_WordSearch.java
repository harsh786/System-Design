import java.util.*;

/**
 * Problem 6: Word Search
 * 
 * Given a 2D board and a word, find if the word exists in the grid.
 * Word can be constructed from sequentially adjacent cells (horizontal/vertical).
 *
 * Approach: DFS/Backtracking from each cell. Mark visited cells in-place by modifying char.
 *
 * Time Complexity: O(m * n * 3^L) where L = word length (3 directions after first step)
 * Space Complexity: O(L) recursion stack
 *
 * Production Analogy: Pattern matching in spatial data - like finding a sequence of
 * connected network hops, or tracing a path through a circuit board layout.
 */
public class Problem06_WordSearch {

    public static boolean exist(char[][] board, String word) {
        int m = board.length, n = board[0].length;
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++)
                if (dfs(board, word, i, j, 0)) return true;
        return false;
    }

    private static boolean dfs(char[][] board, String word, int i, int j, int k) {
        if (k == word.length()) return true;
        if (i < 0 || i >= board.length || j < 0 || j >= board[0].length || board[i][j] != word.charAt(k))
            return false;
        char tmp = board[i][j];
        board[i][j] = '#';
        boolean found = dfs(board, word, i+1, j, k+1) || dfs(board, word, i-1, j, k+1)
                     || dfs(board, word, i, j+1, k+1) || dfs(board, word, i, j-1, k+1);
        board[i][j] = tmp;
        return found;
    }

    public static void main(String[] args) {
        char[][] board = {{'A','B','C','E'},{'S','F','C','S'},{'A','D','E','E'}};
        System.out.println("Test 1 (ABCCED): " + exist(board, "ABCCED")); // true
        System.out.println("Test 2 (SEE): " + exist(board, "SEE"));       // true
        System.out.println("Test 3 (ABCB): " + exist(board, "ABCB"));     // false
        char[][] board2 = {{'a'}};
        System.out.println("Test 4 (a): " + exist(board2, "a"));          // true
    }
}
