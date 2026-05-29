/**
 * Problem 37: Delete Word from Trie
 * 
 * Implement delete operation for Trie. Must handle:
 * - Word is prefix of another (just unmark isEnd)
 * - Word has shared prefix (delete only unique suffix nodes)
 * - Word is unique (delete all nodes)
 * 
 * Time Complexity: O(m) where m = word length
 * Space Complexity: O(m) recursion stack
 * 
 * Production Analogy: Cache eviction, dictionary maintenance, unsubscribing from topics,
 * removing routes from routing table.
 */
public class Problem37_DeleteWordFromTrie {

    static class TrieNode {
        TrieNode[] children = new TrieNode[26];
        boolean isEnd = false;

        boolean hasChildren() {
            for (TrieNode c : children) if (c != null) return true;
            return false;
        }
    }

    static class Trie {
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

        boolean search(String word) {
            TrieNode node = root;
            for (char c : word.toCharArray()) {
                int idx = c - 'a';
                if (node.children[idx] == null) return false;
                node = node.children[idx];
            }
            return node.isEnd;
        }

        void delete(String word) {
            delete(root, word, 0);
        }

        // Returns true if parent should delete this node
        boolean delete(TrieNode node, String word, int depth) {
            if (node == null) return false;
            if (depth == word.length()) {
                node.isEnd = false;
                return !node.hasChildren();
            }
            int idx = word.charAt(depth) - 'a';
            if (delete(node.children[idx], word, depth + 1)) {
                node.children[idx] = null;
                return !node.isEnd && !node.hasChildren();
            }
            return false;
        }
    }

    public static void main(String[] args) {
        Trie trie = new Trie();
        trie.insert("apple");
        trie.insert("app");
        System.out.println(trie.search("apple")); // true
        trie.delete("apple");
        System.out.println(trie.search("apple")); // false
        System.out.println(trie.search("app"));   // true (still exists)
        trie.delete("app");
        System.out.println(trie.search("app"));   // false

        trie.insert("hello");
        trie.insert("help");
        trie.delete("hello");
        System.out.println(trie.search("hello")); // false
        System.out.println(trie.search("help"));  // true
    }
}
