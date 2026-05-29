/**
 * Problem 12: Hamming Distance
 * Number of positions where corresponding bits differ.
 * 
 * Approach: XOR then count set bits.
 * Time: O(1), Space: O(1)
 * 
 * Production Analogy: Measuring config drift between two server configurations.
 */
public class Problem12_HammingDistance {
    public static int hammingDistance(int x, int y) {
        int xor = x ^ y;
        int count = 0;
        while (xor != 0) {
            xor &= (xor - 1);
            count++;
        }
        return count;
    }

    public static void main(String[] args) {
        System.out.println(hammingDistance(1, 4)); // 2
        System.out.println(hammingDistance(3, 1)); // 1
        System.out.println(hammingDistance(0, 0)); // 0
    }
}
