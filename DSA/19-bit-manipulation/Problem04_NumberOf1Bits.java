/**
 * Problem 4: Number of 1 Bits (Hamming Weight)
 * Count set bits in an integer.
 * 
 * Approach: n & (n-1) clears lowest set bit. Count iterations.
 * Time: O(k) where k = number of set bits, Space: O(1)
 * 
 * Production Analogy: Counting active feature flags in a bitmask config.
 */
public class Problem04_NumberOf1Bits {
    public static int hammingWeight(int n) {
        int count = 0;
        while (n != 0) {
            n &= (n - 1); // Clear lowest set bit
            count++;
        }
        return count;
    }

    public static void main(String[] args) {
        System.out.println(hammingWeight(11)); // 3 (1011)
        System.out.println(hammingWeight(128)); // 1
        System.out.println(hammingWeight(-3)); // 31 (all 1s except last bit... actually 11111...101 = 31)
        System.out.println(hammingWeight(0)); // 0
    }
}
