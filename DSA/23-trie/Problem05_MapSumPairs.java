import java.util.*;

/**
 * Problem 5: Map Sum Pairs
 * 
 * Implement MapSum class with insert(key, val) and sum(prefix) methods.
 * sum returns the sum of all values whose key starts with the given prefix.
 * 
 * Time Complexity: Insert O(m), Sum O(m) where m = key/prefix length
 * Space Complexity: O(n * m)
 * 
 * Production Analogy: Analytics dashboards aggregating metrics by category prefix,
 * e-commerce product category revenue rollups, hierarchical budget systems.
 */
public class Problem05_MapSumPairs {

    static class TrieNode {
        TrieNode[] children = new TrieNode[26];
        int prefixSum = 0;
    }

    static class MapSum {
        TrieNode root = new TrieNode();
        Map<String, Integer> map = new HashMap<>();

        public void insert(String key, int val) {
            int delta = val - map.getOrDefault(key, 0);
            map.put(key, val);
            TrieNode node = root;
            for (char c : key.toCharArray()) {
                int idx = c - 'a';
                if (node.children[idx] == null) node.children[idx] = new TrieNode();
                node = node.children[idx];
                node.prefixSum += delta;
            }
        }

        public int sum(String prefix) {
            TrieNode node = root;
            for (char c : prefix.toCharArray()) {
                int idx = c - 'a';
                if (node.children[idx] == null) return 0;
                node = node.children[idx];
            }
            return node.prefixSum;
        }
    }

    public static void main(String[] args) {
        MapSum ms = new MapSum();
        ms.insert("apple", 3);
        System.out.println(ms.sum("ap")); // 3
        ms.insert("app", 2);
        System.out.println(ms.sum("ap")); // 5
        ms.insert("apple", 5); // update
        System.out.println(ms.sum("ap")); // 7
        System.out.println(ms.sum("b"));  // 0
    }
}
