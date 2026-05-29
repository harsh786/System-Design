import java.util.*;

/**
 * Problem 3: Word Search II
 * 
 * Given a 2D board of characters and a list of words, find all words in the board.
 * Each word must be constructed from letters of sequentially adjacent cells (horizontal/vertical).
 * 
 * Time Complexity: O(M*N * 4^L) where M*N is board size, L is max word length
 * Space Complexity: O(sum of word lengths) for the trie
 * 
 * Production Analogy: Pattern detection in grid-based data (image processing, OCR),
 * game engines for word puzzle games like Boggle/Scrabble.
 */
public class Problem03_WordSearchII {

    static class TrieNode {
        TrieNode[] children = new TrieNode[26];
        String word = null; // Store complete word at end node for easy retrieval
    }

    static TrieNode buildTrie(String[] words) {
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
        return root;
    }

    public static List<String> findWords(char[][] board, String[] words) {
        List<String> result = new ArrayList<>();
        TrieNode root = buildTrie(words);
        for (int i = 0; i < board.length; i++) {
            for (int j = 0; j < board[0].length; j++) {
                dfs(board, i, j, root, result);
            }
        }
        return result;
    }

    static void dfs(char[][] board, int i, int j, TrieNode node, List<String> result) {
        if (i < 0 || i >= board.length || j < 0 || j >= board[0].length) return;
        char c = board[i][j];
        if (c == '#' || node.children[c - 'a'] == null) return;
        node = node.children[c - 'a'];
        if (node.word != null) {
            result.add(node.word);
            node.word = null; // avoid duplicates
        }
        board[i][j] = '#'; // mark visited
        dfs(board, i + 1, j, node, result);
        dfs(board, i - 1, j, node, result);
        dfs(board, i, j + 1, node, result);
        dfs(board, i, j - 1, node, result);
        board[i][j] = c; // restore
    }

    public static void main(String[] args) {
        char[][] board = {
            {'o','a','a','n'},
            {'e','t','a','e'},
            {'i','h','k','r'},
            {'i','f','l','v'}
        };
        String[] words = {"oath","pea","eat","rain"};
        System.out.println(findWords(board, words)); // [oath, eat]

        char[][] board2 = {{'a','b'},{'c','d'}};
        String[] words2 = {"abcb"};
        System.out.println(findWords(board2, words2)); // []
    }
}
