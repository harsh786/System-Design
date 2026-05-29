/**
 * Problem 33: Trie with Wildcard Dot Search
 * 
 * Extended wildcard search supporting '.' (any single char) and '*' (any sequence).
 * 
 * Time Complexity: O(26^m) worst case with wildcards, O(m) best case
 * Space Complexity: O(n*m) for trie
 * 
 * Production Analogy: File glob matching (*.java), regex engines,
 * network ACL rules (192.168.*.*), topic subscriptions in pub/sub (MQTT).
 */
public class Problem33_WildcardDotSearch {

    static class TrieNode {
        TrieNode[] children = new TrieNode[26];
        boolean isEnd = false;
    }

    static class WildcardTrie {
        TrieNode root = new TrieNode();

        void insert(String word) {
            TrieNode node = root;
            for (char c : word.toCharArray()) {
                int idx = c - 'a';
                if (node.children[idx] == null) node.children[idx] = new TrieNode();
                node = node.children[idx];
            }
            node.isEnd = true;
        }

        // Search with '.' = any single char, '*' = any sequence (including empty)
        boolean search(String pattern) {
            return match(pattern, 0, root);
        }

        boolean match(String pattern, int i, TrieNode node) {
            if (node == null) return false;
            if (i == pattern.length()) return node.isEnd;
            char c = pattern.charAt(i);
            if (c == '*') {
                // '*' matches empty or one char + continue with '*'
                if (match(pattern, i + 1, node)) return true; // match empty
                for (TrieNode child : node.children) {
                    if (child != null) {
                        if (match(pattern, i, child)) return true; // consume one char, keep '*'
                    }
                }
                return false;
            } else if (c == '.') {
                for (TrieNode child : node.children) {
                    if (child != null && match(pattern, i + 1, child)) return true;
                }
                return false;
            } else {
                return match(pattern, i + 1, node.children[c - 'a']);
            }
        }
    }

    public static void main(String[] args) {
        WildcardTrie trie = new WildcardTrie();
        trie.insert("hello");
        trie.insert("help");
        trie.insert("world");
        System.out.println(trie.search("hel.o"));  // true (hello)
        System.out.println(trie.search("hel*"));   // true (hello, help)
        System.out.println(trie.search("*orld"));  // true (world)
        System.out.println(trie.search("h*p"));    // true (help)
        System.out.println(trie.search("h*z"));    // false
        System.out.println(trie.search("...lo"));  // true (hello)
        System.out.println(trie.search("*"));      // true (matches any)
    }
}
