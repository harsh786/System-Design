/**
 * Problem 6: Reverse Bits
 * Reverse bits of a 32-bit unsigned integer.
 * 
 * Approach: Shift result left, append last bit of n, shift n right. Repeat 32 times.
 * Time: O(32) = O(1), Space: O(1)
 * 
 * Production Analogy: Reversing priority encoding in network packet headers.
 */
public class Problem06_ReverseBits {
    public static int reverseBits(int n) {
        int result = 0;
        for (int i = 0; i < 32; i++) {
            result = (result << 1) | (n & 1);
            n >>>= 1; // unsigned right shift
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(Integer.toUnsignedString(reverseBits(0b00000010100101000001111010011100)));
        // Expected: 964176192 (00111001011110000010100101000000)
        System.out.println(reverseBits(0)); // 0
        System.out.println(Integer.toUnsignedString(reverseBits(-1))); // 4294967295 (all 1s)
    }
}
