import java.util.*;

/**
 * Problem 11: Implement Trie (Prefix Tree)
 * 
 * API Contract:
 * - insert(word): Insert word
 * - search(word): Return true if exact word exists
 * - startsWith(prefix): Return true if any word has given prefix
 * 
 * Complexity: O(L) for all operations where L = word length
 * Data Structure: Array of 26 children per node + isEnd flag
 * 
 * Production Analogy: Autocomplete systems, IP routing tables (longest prefix match),
 * spell checkers, phone contact search
 */
public class Problem11_ImplementTrie {

    static class Trie {
        private Trie[] children = new Trie[26];
        private boolean isEnd;

        public void insert(String word) {
            Trie node = this;
            for (char c : word.toCharArray()) {
                if (node.children[c - 'a'] == null)
                    node.children[c - 'a'] = new Trie();
                node = node.children[c - 'a'];
            }
            node.isEnd = true;
        }

        public boolean search(String word) {
            Trie node = find(word);
            return node != null && node.isEnd;
        }

        public boolean startsWith(String prefix) {
            return find(prefix) != null;
        }

        private Trie find(String s) {
            Trie node = this;
            for (char c : s.toCharArray()) {
                if (node.children[c - 'a'] == null) return null;
                node = node.children[c - 'a'];
            }
            return node;
        }
    }

    public static void main(String[] args) {
        Trie trie = new Trie();
        trie.insert("apple");
        assert trie.search("apple");
        assert !trie.search("app");
        assert trie.startsWith("app");
        trie.insert("app");
        assert trie.search("app");
        assert !trie.search("apples");
        assert !trie.startsWith("b");

        System.out.println("All tests passed!");
    }
}
