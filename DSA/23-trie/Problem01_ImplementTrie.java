/**
 * Problem 1: Implement Trie (Prefix Tree)
 * 
 * A Trie is a tree-like data structure used for efficient retrieval of keys in a dataset of strings.
 * 
 * Operations: insert, search, startsWith
 * 
 * Time Complexity: O(m) for each operation where m = length of word
 * Space Complexity: O(n * m) where n = number of words, m = average length
 * 
 * Production Analogy: Autocomplete systems in search engines (Google, IDE code completion),
 * spell checkers, IP routing tables, phone directories.
 */
public class Problem01_ImplementTrie {

    static class TrieNode {
        TrieNode[] children = new TrieNode[26];
        boolean isEndOfWord = false;
    }

    static class Trie {
        private TrieNode root;

        public Trie() {
            root = new TrieNode();
        }

        // Insert a word into the trie - O(m) time
        public void insert(String word) {
            TrieNode node = root;
            for (char c : word.toCharArray()) {
                int idx = c - 'a';
                if (node.children[idx] == null) {
                    node.children[idx] = new TrieNode();
                }
                node = node.children[idx];
            }
            node.isEndOfWord = true;
        }

        // Search for exact word - O(m) time
        public boolean search(String word) {
            TrieNode node = searchPrefix(word);
            return node != null && node.isEndOfWord;
        }

        // Check if any word starts with given prefix - O(m) time
        public boolean startsWith(String prefix) {
            return searchPrefix(prefix) != null;
        }

        private TrieNode searchPrefix(String prefix) {
            TrieNode node = root;
            for (char c : prefix.toCharArray()) {
                int idx = c - 'a';
                if (node.children[idx] == null) return null;
                node = node.children[idx];
            }
            return node;
        }
    }

    public static void main(String[] args) {
        Trie trie = new Trie();
        trie.insert("apple");
        System.out.println(trie.search("apple"));    // true
        System.out.println(trie.search("app"));      // false
        System.out.println(trie.startsWith("app"));  // true
        trie.insert("app");
        System.out.println(trie.search("app"));      // true

        // Edge cases
        trie.insert("");
        System.out.println(trie.search(""));         // true
        System.out.println(trie.search("b"));        // false
        System.out.println(trie.startsWith("apple")); // true
        System.out.println(trie.startsWith("apx"));   // false
    }
}
