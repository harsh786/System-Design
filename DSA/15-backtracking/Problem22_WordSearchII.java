import java.util.*;

/**
 * Problem 22: Word Search II (LeetCode 212)
 * 
 * Find all words from a dictionary that exist in a 2D board.
 * 
 * Search Tree:
 * - Build a Trie from words, then DFS from each cell
 * - At each cell, follow Trie children; if node is a word end, add to result
 * 
 * Pruning Strategy:
 * - Trie prunes paths that don't match any word prefix
 * - Remove found words from Trie to avoid duplicate results
 * - Mark visited cells in-place
 * 
 * Time Complexity: O(m*n * 4 * 3^(L-1)) per DFS start, but Trie limits exploration
 * Space Complexity: O(total chars in all words) for Trie
 * 
 * Production Analogy:
 * - Multi-pattern matching in network security: scanning data streams for multiple threat signatures.
 */
public class Problem22_WordSearchII {

    class TrieNode {
        TrieNode[] children = new TrieNode[26];
        String word = null;
    }

    public List<String> findWords(char[][] board, String[] words) {
        TrieNode root = new TrieNode();
        for (String w : words) {
            TrieNode node = root;
            for (char c : w.toCharArray()) {
                int idx = c - 'a';
                if (node.children[idx] == null) node.children[idx] = new TrieNode();
                node = node.children[idx];
            }
            node.word = w;
        }

        List<String> result = new ArrayList<>();
        for (int i = 0; i < board.length; i++)
            for (int j = 0; j < board[0].length; j++)
                dfs(board, i, j, root, result);
        return result;
    }

    private void dfs(char[][] board, int i, int j, TrieNode node, List<String> result) {
        if (i < 0 || i >= board.length || j < 0 || j >= board[0].length) return;
        char c = board[i][j];
        if (c == '#' || node.children[c - 'a'] == null) return;

        node = node.children[c - 'a'];
        if (node.word != null) {
            result.add(node.word);
            node.word = null; // avoid duplicates
        }

        board[i][j] = '#';
        dfs(board, i+1, j, node, result);
        dfs(board, i-1, j, node, result);
        dfs(board, i, j+1, node, result);
        dfs(board, i, j-1, node, result);
        board[i][j] = c;
    }

    public static void main(String[] args) {
        Problem22_WordSearchII sol = new Problem22_WordSearchII();

        char[][] board = {{'o','a','a','n'},{'e','t','a','e'},{'i','h','k','r'},{'i','f','l','v'}};
        System.out.println(sol.findWords(board, new String[]{"oath","pea","eat","rain"}));
        // [oath, eat]

        char[][] board2 = {{'a','b'},{'c','d'}};
        System.out.println(sol.findWords(board2, new String[]{"abcb"})); // []
    }
}
