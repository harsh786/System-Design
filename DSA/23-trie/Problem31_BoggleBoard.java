import java.util.*;

/**
 * Problem 31: Trie for Boggle Board
 * 
 * Find all valid words from a dictionary that can be formed on a Boggle board
 * (8-directional adjacency, each cell used at most once per word).
 * 
 * Time Complexity: O(M*N * 8^L * W) optimized with trie pruning
 * Space Complexity: O(W * L) for trie where W = dictionary words, L = max length
 * 
 * Production Analogy: Word game engines (Scrabble, Boggle apps), OCR word detection,
 * spatial text recognition in AR applications.
 */
public class Problem31_BoggleBoard {

    static class TrieNode {
        TrieNode[] children = new TrieNode[26];
        String word = null;
    }

    static int[][] dirs = {{-1,-1},{-1,0},{-1,1},{0,-1},{0,1},{1,-1},{1,0},{1,1}};

    public static List<String> findWords(char[][] board, String[] dictionary) {
        TrieNode root = new TrieNode();
        for (String w : dictionary) {
            TrieNode node = root;
            for (char c : w.toCharArray()) {
                int idx = c - 'a';
                if (node.children[idx] == null) node.children[idx] = new TrieNode();
                node = node.children[idx];
            }
            node.word = w;
        }

        Set<String> result = new HashSet<>();
        for (int i = 0; i < board.length; i++)
            for (int j = 0; j < board[0].length; j++)
                dfs(board, i, j, root, result);
        return new ArrayList<>(result);
    }

    static void dfs(char[][] board, int i, int j, TrieNode node, Set<String> result) {
        if (i < 0 || i >= board.length || j < 0 || j >= board[0].length) return;
        char c = board[i][j];
        if (c == '#' || node.children[c - 'a'] == null) return;
        node = node.children[c - 'a'];
        if (node.word != null) result.add(node.word);
        board[i][j] = '#';
        for (int[] d : dirs) dfs(board, i + d[0], j + d[1], node, result);
        board[i][j] = c;
    }

    public static void main(String[] args) {
        char[][] board = {
            {'g','i','z'},
            {'u','e','k'},
            {'q','s','e'}
        };
        String[] dict = {"geek","quiz","geeks","seek","que"};
        System.out.println(findWords(board, dict));
    }
}
