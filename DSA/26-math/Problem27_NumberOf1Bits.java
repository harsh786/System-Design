/**
 * Problem 27: Number of 1 Bits (Hamming Weight)
 * Count the number of '1' bits in an integer.
 *
 * Approach: n & (n-1) clears the lowest set bit. Count iterations.
 * Time Complexity: O(k) where k is number of set bits
 * Space Complexity: O(1)
 *
 * Production Analogy: Like counting active flags in a bitmask permission system.
 */
public class Problem27_NumberOf1Bits {

    public static int hammingWeight(int n) {
        int count = 0;
        while (n != 0) {
            n &= (n - 1);
            count++;
        }
        return count;
    }

    public static void main(String[] args) {
        System.out.println(hammingWeight(11));          // 3
        System.out.println(hammingWeight(128));         // 1
        System.out.println(hammingWeight(-3));          // 31
        System.out.println(hammingWeight(0));           // 0
        System.out.println(hammingWeight(Integer.MAX_VALUE)); // 31
    }
}
