import java.util.*;

/**
 * Problem 10: Design Add and Search Words Data Structure
 * 
 * API Contract:
 * - addWord(word): Add word to dictionary
 * - search(word): Search with '.' as wildcard for any single character
 * 
 * Complexity: addWord O(L), search O(26^dots * L) worst case
 * Data Structure: Trie with DFS for wildcard matching
 * 
 * Production Analogy: Regex engines, DNS wildcard matching,
 * autocomplete with fuzzy matching, spam filter pattern matching
 */
public class Problem10_AddSearchWordsDataStructure {

    static class WordDictionary {
        private class TrieNode {
            TrieNode[] children = new TrieNode[26];
            boolean isEnd;
        }

        private TrieNode root;

        public WordDictionary() { root = new TrieNode(); }

        public void addWord(String word) {
            TrieNode node = root;
            for (char c : word.toCharArray()) {
                if (node.children[c - 'a'] == null)
                    node.children[c - 'a'] = new TrieNode();
                node = node.children[c - 'a'];
            }
            node.isEnd = true;
        }

        public boolean search(String word) {
            return dfs(word, 0, root);
        }

        private boolean dfs(String word, int idx, TrieNode node) {
            if (node == null) return false;
            if (idx == word.length()) return node.isEnd;
            char c = word.charAt(idx);
            if (c == '.') {
                for (TrieNode child : node.children)
                    if (dfs(word, idx + 1, child)) return true;
                return false;
            }
            return dfs(word, idx + 1, node.children[c - 'a']);
        }
    }

    public static void main(String[] args) {
        WordDictionary wd = new WordDictionary();
        wd.addWord("bad");
        wd.addWord("dad");
        wd.addWord("mad");
        assert !wd.search("pad");
        assert wd.search("bad");
        assert wd.search(".ad");
        assert wd.search("b..");
        assert !wd.search("b.x");
        assert wd.search("...");
        assert !wd.search("....");

        System.out.println("All tests passed!");
    }
}
