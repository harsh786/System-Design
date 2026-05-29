import java.util.*;

/**
 * Problem 12: Word Squares
 * 
 * Given a set of words of same length, find all word squares (word[i][j] == word[j][i]).
 * Use trie to efficiently find words with a given prefix.
 * 
 * Time Complexity: O(n * 26^L) worst case, much better with prefix pruning
 * Space Complexity: O(n * L) for trie
 * 
 * Production Analogy: Crossword puzzle generation, grid-based layout engines,
 * matrix symmetry validation in linear algebra solvers.
 */
public class Problem12_WordSquares {

    static class TrieNode {
        TrieNode[] children = new TrieNode[26];
        List<String> wordsWithPrefix = new ArrayList<>();
    }

    static TrieNode root;

    static void insert(String word) {
        TrieNode node = root;
        node.wordsWithPrefix.add(word);
        for (char c : word.toCharArray()) {
            int idx = c - 'a';
            if (node.children[idx] == null) node.children[idx] = new TrieNode();
            node = node.children[idx];
            node.wordsWithPrefix.add(word);
        }
    }

    static List<String> getWordsWithPrefix(String prefix) {
        TrieNode node = root;
        for (char c : prefix.toCharArray()) {
            int idx = c - 'a';
            if (node.children[idx] == null) return new ArrayList<>();
            node = node.children[idx];
        }
        return node.wordsWithPrefix;
    }

    public static List<List<String>> wordSquares(String[] words) {
        root = new TrieNode();
        for (String w : words) insert(w);
        List<List<String>> result = new ArrayList<>();
        int len = words[0].length();

        for (String w : words) {
            List<String> square = new ArrayList<>();
            square.add(w);
            backtrack(square, len, result);
        }
        return result;
    }

    static void backtrack(List<String> square, int len, List<List<String>> result) {
        if (square.size() == len) { result.add(new ArrayList<>(square)); return; }
        int idx = square.size();
        StringBuilder prefix = new StringBuilder();
        for (String w : square) prefix.append(w.charAt(idx));
        for (String candidate : getWordsWithPrefix(prefix.toString())) {
            square.add(candidate);
            backtrack(square, len, result);
            square.remove(square.size() - 1);
        }
    }

    public static void main(String[] args) {
        System.out.println(wordSquares(new String[]{"area","lead","wall","lady","ball"}));
        // [[wall,area,lead,lady],[ball,area,lead,lady]]
        System.out.println(wordSquares(new String[]{"abat","baba","atan","atal"}));
    }
}
