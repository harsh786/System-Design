/**
 * Problem 9: Maximum XOR of Two Numbers in an Array
 * 
 * Given an integer array, find the maximum XOR of any two elements.
 * Use a binary trie (bit trie) to greedily find the max XOR.
 * 
 * Time Complexity: O(n * 32) = O(n)
 * Space Complexity: O(n * 32) = O(n)
 * 
 * Production Analogy: Network subnet calculations, cryptographic hash comparisons,
 * error detection codes, FPGA routing optimization.
 */
public class Problem09_MaximumXOR {

    static class TrieNode {
        TrieNode[] children = new TrieNode[2]; // binary: 0 or 1
    }

    public static int findMaximumXOR(int[] nums) {
        TrieNode root = new TrieNode();
        // Insert all numbers into binary trie (MSB first)
        for (int num : nums) {
            TrieNode node = root;
            for (int i = 31; i >= 0; i--) {
                int bit = (num >> i) & 1;
                if (node.children[bit] == null) node.children[bit] = new TrieNode();
                node = node.children[bit];
            }
        }

        int maxXor = 0;
        for (int num : nums) {
            TrieNode node = root;
            int xor = 0;
            for (int i = 31; i >= 0; i--) {
                int bit = (num >> i) & 1;
                int oppBit = 1 - bit; // we want opposite bit to maximize XOR
                if (node.children[oppBit] != null) {
                    xor |= (1 << i);
                    node = node.children[oppBit];
                } else {
                    node = node.children[bit];
                }
            }
            maxXor = Math.max(maxXor, xor);
        }
        return maxXor;
    }

    public static void main(String[] args) {
        System.out.println(findMaximumXOR(new int[]{3,10,5,25,2,8})); // 28 (5^25)
        System.out.println(findMaximumXOR(new int[]{14,70,53,83,49,91,36,80,92,51,66,70})); // 127
        System.out.println(findMaximumXOR(new int[]{0})); // 0
        System.out.println(findMaximumXOR(new int[]{1,2})); // 3
    }
}
