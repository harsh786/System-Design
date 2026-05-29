/**
 * Problem 26: Binary Number with Alternating Bits
 * 
 * Approach: n ^ (n>>1) should be all 1s. Check (x & (x+1)) == 0.
 * Time: O(1), Space: O(1)
 * 
 * Production Analogy: Validating clock signal integrity (alternating high/low).
 */
public class Problem26_AlternatingBits {
    public static boolean hasAlternatingBits(int n) {
        int x = n ^ (n >> 1); // should be all 1s
        return (x & (x + 1)) == 0;
    }

    public static void main(String[] args) {
        System.out.println(hasAlternatingBits(5)); // true (101)
        System.out.println(hasAlternatingBits(7)); // false (111)
        System.out.println(hasAlternatingBits(10)); // true (1010)
        System.out.println(hasAlternatingBits(11)); // false
    }
}
