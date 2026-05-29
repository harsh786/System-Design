import java.util.*;

/**
 * Problem 44: Trie Memory Optimization
 * 
 * Compare different trie implementations for memory efficiency:
 * 1. Array-based (26 children) - fast but memory-heavy
 * 2. HashMap-based - memory-efficient for sparse tries
 * 3. Sorted array of (char, node) pairs - balanced approach
 * 
 * Time Complexity: Array O(1) lookup, HashMap O(1) amortized, Sorted O(log k) where k=children
 * Space Complexity: Array O(26*n), HashMap O(actual_children*n), Sorted O(actual_children*n)
 * 
 * Production Analogy: Mobile app memory constraints, embedded systems,
 * large-scale autocomplete (billions of entries), memory-mapped trie files.
 */
public class Problem44_TrieMemoryOptimization {

    // Approach 1: Standard array-based TrieNode
    static class TrieNode {
        TrieNode[] children = new TrieNode[26]; // 26 pointers always allocated
        boolean isEnd = false;
    }

    // Approach 2: HashMap-based (only stores actual children)
    static class CompactTrieNode {
        Map<Character, CompactTrieNode> children = new HashMap<>(4); // initial capacity 4
        boolean isEnd = false;
    }

    // Approach 3: Flat array trie (all nodes in single array for cache locality)
    static class FlatTrie {
        int[][] children; // children[nodeId][charIdx] = childNodeId
        boolean[] isEnd;
        int size = 0;
        int capacity;

        FlatTrie(int maxNodes) {
            capacity = maxNodes;
            children = new int[maxNodes][26];
            isEnd = new boolean[maxNodes];
            for (int[] row : children) Arrays.fill(row, -1);
            size = 1; // root is node 0
        }

        void insert(String word) {
            int node = 0;
            for (char c : word.toCharArray()) {
                int idx = c - 'a';
                if (children[node][idx] == -1) {
                    children[node][idx] = size++;
                }
                node = children[node][idx];
            }
            isEnd[node] = true;
        }

        boolean search(String word) {
            int node = 0;
            for (char c : word.toCharArray()) {
                int idx = c - 'a';
                if (children[node][idx] == -1) return false;
                node = children[node][idx];
            }
            return isEnd[node];
        }
    }

    public static void main(String[] args) {
        String[] words = {"apple","app","application","bat","ball","banana"};

        // Test FlatTrie
        FlatTrie flat = new FlatTrie(100);
        for (String w : words) flat.insert(w);
        System.out.println("FlatTrie nodes used: " + flat.size);
        System.out.println(flat.search("apple"));      // true
        System.out.println(flat.search("app"));        // true
        System.out.println(flat.search("application"));// true
        System.out.println(flat.search("ap"));         // false
        System.out.println(flat.search("ban"));        // false

        // Memory comparison
        System.out.println("\nMemory Analysis (approximate):");
        System.out.println("Array-based: " + flat.size + " nodes * 26 * 4 bytes = " + (flat.size * 26 * 4) + " bytes");
        System.out.println("HashMap-based: much less for sparse tries, more for dense");
        System.out.println("Flat array: best cache locality, worst flexibility");
    }
}
