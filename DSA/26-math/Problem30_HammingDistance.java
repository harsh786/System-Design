/**
 * Problem 30: Hamming Distance
 * Count positions where corresponding bits differ between two integers.
 *
 * Approach: XOR then count set bits.
 * Time Complexity: O(1)
 * Space Complexity: O(1)
 *
 * Production Analogy: Like error detection in ECC memory - counting bit flips
 * between expected and actual values.
 */
public class Problem30_HammingDistance {

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
        System.out.println(hammingDistance(1, 4));  // 2
        System.out.println(hammingDistance(3, 1));  // 1
        System.out.println(hammingDistance(0, 0));  // 0
    }
}
