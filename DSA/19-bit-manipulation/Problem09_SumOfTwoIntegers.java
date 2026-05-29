/**
 * Problem 9: Sum of Two Integers (without + or -)
 * 
 * Approach: XOR gives sum without carry. AND<<1 gives carry. Repeat until no carry.
 * Time: O(32) = O(1), Space: O(1)
 * 
 * Production Analogy: Hardware adder circuit implementation (half-adder + full-adder).
 */
public class Problem09_SumOfTwoIntegers {
    public static int getSum(int a, int b) {
        while (b != 0) {
            int carry = (a & b) << 1;
            a = a ^ b; // sum without carry
            b = carry;
        }
        return a;
    }

    public static void main(String[] args) {
        System.out.println(getSum(1, 2)); // 3
        System.out.println(getSum(-1, 1)); // 0
        System.out.println(getSum(0, 0)); // 0
        System.out.println(getSum(-12, -8)); // -20
    }
}
