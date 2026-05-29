/**
 * Problem 14: Integer Break
 * Break integer n into at least two positive integers that maximize product.
 *
 * Approach: Math insight - use as many 3s as possible (unless remainder is 1, use 2+2).
 * Time Complexity: O(n/3) or O(1) with pow
 * Space Complexity: O(1)
 *
 * Production Analogy: Like optimal resource partitioning in load balancing -
 * splitting evenly maximizes throughput.
 */
public class Problem14_IntegerBreak {

    public static int integerBreak(int n) {
        if (n == 2) return 1;
        if (n == 3) return 2;

        int product = 1;
        while (n > 4) {
            product *= 3;
            n -= 3;
        }
        return product * n;
    }

    public static void main(String[] args) {
        System.out.println(integerBreak(2));   // 1
        System.out.println(integerBreak(10));  // 36
        System.out.println(integerBreak(3));   // 2
        System.out.println(integerBreak(8));   // 18
        System.out.println(integerBreak(58));  // large
    }
}
