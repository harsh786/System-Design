/**
 * Problem 20: Count Pairs With XOR in a Range
 * 
 * Count pairs (i,j) where i<j and low <= nums[i] XOR nums[j] <= high.
 * Use binary trie with subtree counts.
 * 
 * Time Complexity: O(n * 15) since numbers <= 2^15
 * Space Complexity: O(n * 15)
 * 
 * Production Analogy: Network anomaly detection (counting IP pairs within distance),
 * similarity search in high-dimensional spaces, hamming distance calculations.
 */
public class Problem20_CountPairsXORInRange {

    static class TrieNode {
        TrieNode[] children = new TrieNode[2];
        int count = 0;
    }

    static TrieNode root;

    static void insert(int num) {
        TrieNode node = root;
        for (int i = 14; i >= 0; i--) {
            int bit = (num >> i) & 1;
            if (node.children[bit] == null) node.children[bit] = new TrieNode();
            node = node.children[bit];
            node.count++;
        }
    }

    // Count pairs with XOR < limit
    static int countLess(int num, int limit) {
        TrieNode node = root;
        int count = 0;
        for (int i = 14; i >= 0; i--) {
            if (node == null) break;
            int numBit = (num >> i) & 1;
            int limBit = (limit >> i) & 1;
            if (limBit == 1) {
                // XOR bit = 0 path contributes count (all less), then go to XOR bit = 1 path
                if (node.children[numBit] != null) count += node.children[numBit].count;
                node = node.children[1 - numBit]; // XOR with this = 1
            } else {
                node = node.children[numBit]; // XOR with this = 0
            }
        }
        return count;
    }

    public static int countPairs(int[] nums, int low, int high) {
        int result = 0;
        root = new TrieNode();
        for (int num : nums) {
            result += countLess(num, high + 1) - countLess(num, low);
            insert(num);
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(countPairs(new int[]{1,4,2,7}, 2, 6)); // 6
        System.out.println(countPairs(new int[]{9,8,4,2,1}, 5, 14)); // 8
        System.out.println(countPairs(new int[]{1,1,1}, 0, 0)); // 3 (all XOR to 0)
    }
}
