/**
 * Problem 28: Binary Trie for Maximum XOR
 * 
 * Given an array, for each element find the maximum XOR with any previous element.
 * Online version of Problem 9 - process elements one by one.
 * 
 * Time Complexity: O(n * 32)
 * Space Complexity: O(n * 32)
 * 
 * Production Analogy: Real-time network traffic analysis (finding most different packet),
 * streaming data anomaly detection, online recommendation divergence scoring.
 */
public class Problem28_BinaryTrieMaxXOR {

    static class TrieNode {
        TrieNode[] children = new TrieNode[2];
    }

    public static int[] maxXorForEach(int[] nums) {
        TrieNode root = new TrieNode();
        int[] result = new int[nums.length];

        // Insert first number
        insert(root, nums[0]);
        result[0] = 0;

        for (int i = 1; i < nums.length; i++) {
            result[i] = query(root, nums[i]);
            insert(root, nums[i]);
        }
        return result;
    }

    static void insert(TrieNode root, int num) {
        TrieNode node = root;
        for (int i = 31; i >= 0; i--) {
            int bit = (num >> i) & 1;
            if (node.children[bit] == null) node.children[bit] = new TrieNode();
            node = node.children[bit];
        }
    }

    static int query(TrieNode root, int num) {
        TrieNode node = root;
        int xor = 0;
        for (int i = 31; i >= 0; i--) {
            int bit = (num >> i) & 1;
            int want = 1 - bit;
            if (node.children[want] != null) {
                xor |= (1 << i);
                node = node.children[want];
            } else {
                node = node.children[bit];
            }
        }
        return xor;
    }

    public static void main(String[] args) {
        int[] result = maxXorForEach(new int[]{3, 10, 5, 25, 2, 8});
        // For each element, max XOR with any previous
        for (int r : result) System.out.print(r + " ");
        System.out.println();
        // 0 9 14 28 27 ...
    }
}
