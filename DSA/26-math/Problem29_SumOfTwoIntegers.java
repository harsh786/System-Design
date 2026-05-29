/**
 * Problem 29: Sum of Two Integers (Bit Manipulation)
 * Calculate sum without using + or - operators.
 *
 * Approach: XOR gives sum without carry. AND shifted left gives carry. Repeat.
 * Time Complexity: O(32) = O(1)
 * Space Complexity: O(1)
 *
 * Production Analogy: Like hardware adder circuits (half-adder / full-adder)
 * that use XOR for sum and AND for carry propagation.
 */
public class Problem29_SumOfTwoIntegers {

    public static int getSum(int a, int b) {
        while (b != 0) {
            int carry = (a & b) << 1;
            a = a ^ b;
            b = carry;
        }
        return a;
    }

    public static void main(String[] args) {
        System.out.println(getSum(1, 2));    // 3
        System.out.println(getSum(-2, 3));   // 1
        System.out.println(getSum(0, 0));    // 0
        System.out.println(getSum(-1, 1));   // 0
        System.out.println(getSum(100, 200));// 300
    }
}
