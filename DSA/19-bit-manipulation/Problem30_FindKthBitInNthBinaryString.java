/**
 * Problem 30: Find Kth Bit in Nth Binary String
 * S1="0", Sn = S(n-1) + "1" + reverse(invert(S(n-1)))
 * 
 * Approach: Recursively determine position. Length = 2^n - 1. Mid = 2^(n-1).
 * Time: O(n), Space: O(n) recursion
 * 
 * Production Analogy: Hierarchical config lookup in fractal-structured distributed systems.
 */
public class Problem30_FindKthBitInNthBinaryString {
    public static char findKthBit(int n, int k) {
        if (n == 1) return '0';
        int len = (1 << n) - 1;
        int mid = len / 2 + 1;
        if (k == mid) return '1';
        if (k < mid) return findKthBit(n - 1, k);
        // Mirror position, inverted
        return findKthBit(n - 1, len - k + 1) == '0' ? '1' : '0';
    }

    public static void main(String[] args) {
        System.out.println(findKthBit(3, 1)); // 0
        System.out.println(findKthBit(4, 11)); // 1
        System.out.println(findKthBit(1, 1)); // 0
        System.out.println(findKthBit(2, 3)); // 1
    }
}
