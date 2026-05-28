import java.util.*;

/**
 * Problem 14: Word Search (LeetCode 79)
 * 
 * Given a 2D board and a word, find if the word exists by adjacent cell traversal.
 * 
 * Search Tree:
 * - Start DFS from every cell matching word[0]
 * - At each cell, explore 4 directions for next character
 * 
 * Pruning Strategy:
 * - Mark visited cells (in-place by changing to '#')
 * - Return false immediately if current char doesn't match
 * 
 * Time Complexity: O(m*n * 3^L) where L = word length (3 directions after first step)
 * Space Complexity: O(L) recursion depth
 * 
 * Production Analogy:
 * - Graph traversal in network topology: finding a specific path through connected nodes.
 */
public class Problem14_WordSearch {

    public boolean exist(char[][] board, String word) {
        int m = board.length, n = board[0].length;
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++)
                if (dfs(board, word, i, j, 0)) return true;
        return false;
    }

    private boolean dfs(char[][] board, String word, int i, int j, int idx) {
        if (idx == word.length()) return true;
        if (i < 0 || i >= board.length || j < 0 || j >= board[0].length) return false;
        if (board[i][j] != word.charAt(idx)) return false;

        char temp = board[i][j];
        board[i][j] = '#'; // mark visited
        boolean found = dfs(board, word, i+1, j, idx+1) || dfs(board, word, i-1, j, idx+1)
                      || dfs(board, word, i, j+1, idx+1) || dfs(board, word, i, j-1, idx+1);
        board[i][j] = temp; // restore
        return found;
    }

    public static void main(String[] args) {
        Problem14_WordSearch sol = new Problem14_WordSearch();

        char[][] board = {{'A','B','C','E'},{'S','F','C','S'},{'A','D','E','E'}};
        System.out.println(sol.exist(board, "ABCCED")); // true
        System.out.println(sol.exist(board, "SEE"));    // true
        System.out.println(sol.exist(board, "ABCB"));   // false
    }
}
