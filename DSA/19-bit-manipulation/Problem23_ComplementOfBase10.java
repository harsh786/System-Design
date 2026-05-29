/**
 * Problem 23: Complement of Base 10 Integer
 * Flip all bits in the binary representation (no leading zeros).
 * 
 * Approach: Find mask with all 1s of same length, XOR with it.
 * Time: O(log n), Space: O(1)
 * 
 * Production Analogy: Inverting permission bitmask to get denied permissions.
 */
public class Problem23_ComplementOfBase10 {
    public static int bitwiseComplement(int n) {
        if (n == 0) return 1;
        int mask = Integer.highestOneBit(n);
        mask = (mask << 1) - 1; // all 1s mask of same bit length
        return n ^ mask;
    }

    public static void main(String[] args) {
        System.out.println(bitwiseComplement(5)); // 2 (101 -> 010)
        System.out.println(bitwiseComplement(7)); // 0 (111 -> 000)
        System.out.println(bitwiseComplement(10)); // 5 (1010 -> 0101)
        System.out.println(bitwiseComplement(0)); // 1
    }
}
