/**
 * Problem 7: Bitwise AND of Numbers Range
 * Return bitwise AND of all numbers in [left, right].
 * 
 * Approach: Find common prefix. Right shift both until equal, then left shift back.
 * Time: O(32) = O(1), Space: O(1)
 * 
 * Production Analogy: Finding common network prefix (subnet mask) for IP range.
 */
public class Problem07_BitwiseANDOfNumbersRange {
    public static int rangeBitwiseAnd(int left, int right) {
        int shift = 0;
        while (left != right) {
            left >>= 1;
            right >>= 1;
            shift++;
        }
        return left << shift;
    }

    public static void main(String[] args) {
        System.out.println(rangeBitwiseAnd(5, 7)); // 4
        System.out.println(rangeBitwiseAnd(0, 0)); // 0
        System.out.println(rangeBitwiseAnd(1, 2147483647)); // 0
    }
}
