import java.util.*;

/**
 * Problem 29: Binary Trie for Minimum XOR Pair
 * 
 * Find the pair of numbers with minimum XOR value.
 * Insight: Min XOR pair is always between adjacent elements when sorted,
 * but trie approach works by finding closest match.
 * 
 * Time Complexity: O(n * 32)
 * Space Complexity: O(n * 32)
 * 
 * Production Analogy: Finding most similar items in recommendation systems,
 * nearest neighbor in hamming space, error correction (closest codeword).
 */
public class Problem29_BinaryTrieMinXORPair {

    static class TrieNode {
        TrieNode[] children = new TrieNode[2];
    }

    static void insert(TrieNode root, int num) {
        TrieNode node = root;
        for (int i = 31; i >= 0; i--) {
            int bit = (num >> i) & 1;
            if (node.children[bit] == null) node.children[bit] = new TrieNode();
            node = node.children[bit];
        }
    }

    static int minXorQuery(TrieNode root, int num) {
        TrieNode node = root;
        int xor = 0;
        for (int i = 31; i >= 0; i--) {
            int bit = (num >> i) & 1;
            if (node.children[bit] != null) {
                node = node.children[bit]; // same bit = 0 XOR
            } else {
                xor |= (1 << i);
                node = node.children[1 - bit];
            }
        }
        return xor;
    }

    public static int findMinXorPair(int[] nums) {
        TrieNode root = new TrieNode();
        insert(root, nums[0]);
        int minXor = Integer.MAX_VALUE;
        for (int i = 1; i < nums.length; i++) {
            minXor = Math.min(minXor, minXorQuery(root, nums[i]));
            insert(root, nums[i]);
        }
        return minXor;
    }

    public static void main(String[] args) {
        System.out.println(findMinXorPair(new int[]{1, 2, 3, 4, 5}));  // 1 (2^3=1 or 4^5=1)
        System.out.println(findMinXorPair(new int[]{9, 5, 3}));         // 6 (9^3=10, 9^5=12, 5^3=6)
        System.out.println(findMinXorPair(new int[]{0, 0}));            // 0
    }
}
