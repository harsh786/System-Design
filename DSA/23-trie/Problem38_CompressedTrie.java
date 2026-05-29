import java.util.*;

/**
 * Problem 38: Compressed Trie (Patricia Trie / Radix Tree)
 * 
 * Compress chains of single-child nodes into one node with edge label.
 * Reduces space significantly for sparse tries.
 * 
 * Time Complexity: O(m) per operation where m = key length
 * Space Complexity: O(n) nodes instead of O(n*m) for standard trie
 * 
 * Production Analogy: Linux kernel routing tables (radix tree), Redis key storage,
 * HTTP router path matching (gorilla/mux, Express.js), IP lookup tables.
 */
public class Problem38_CompressedTrie {

    static class TrieNode {
        Map<Character, TrieNode> children = new HashMap<>();
        String edgeLabel = ""; // label on edge from parent to this node
        boolean isEnd = false;
    }

    static class CompressedTrie {
        TrieNode root = new TrieNode();

        void insert(String word) {
            TrieNode node = root;
            int i = 0;
            while (i < word.length()) {
                char c = word.charAt(i);
                if (!node.children.containsKey(c)) {
                    TrieNode newNode = new TrieNode();
                    newNode.edgeLabel = word.substring(i);
                    newNode.isEnd = true;
                    node.children.put(c, newNode);
                    return;
                }
                TrieNode child = node.children.get(c);
                String label = child.edgeLabel;
                int j = 0;
                while (j < label.length() && i < word.length() && label.charAt(j) == word.charAt(i)) {
                    j++; i++;
                }
                if (j == label.length()) {
                    node = child; // fully matched edge, continue
                } else {
                    // Split the edge
                    TrieNode splitNode = new TrieNode();
                    splitNode.edgeLabel = label.substring(0, j);
                    node.children.put(c, splitNode);

                    child.edgeLabel = label.substring(j);
                    splitNode.children.put(label.charAt(j), child);

                    if (i == word.length()) {
                        splitNode.isEnd = true;
                    } else {
                        TrieNode newNode = new TrieNode();
                        newNode.edgeLabel = word.substring(i);
                        newNode.isEnd = true;
                        splitNode.children.put(word.charAt(i), newNode);
                    }
                    return;
                }
            }
            node.isEnd = true;
        }

        boolean search(String word) {
            TrieNode node = root;
            int i = 0;
            while (i < word.length()) {
                char c = word.charAt(i);
                if (!node.children.containsKey(c)) return false;
                TrieNode child = node.children.get(c);
                String label = child.edgeLabel;
                for (int j = 0; j < label.length(); j++, i++) {
                    if (i >= word.length() || word.charAt(i) != label.charAt(j)) return false;
                }
                node = child;
            }
            return node.isEnd;
        }
    }

    public static void main(String[] args) {
        CompressedTrie trie = new CompressedTrie();
        trie.insert("romane");
        trie.insert("romanus");
        trie.insert("romulus");
        trie.insert("rubens");
        trie.insert("ruber");
        trie.insert("rubicon");

        System.out.println(trie.search("romane"));  // true
        System.out.println(trie.search("romanus")); // true
        System.out.println(trie.search("roman"));   // false
        System.out.println(trie.search("rubens"));  // true
        System.out.println(trie.search("rube"));    // false
        System.out.println(trie.search("rubicon")); // true
    }
}
