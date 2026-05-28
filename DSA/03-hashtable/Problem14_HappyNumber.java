import java.util.*;

/**
 * Problem 14: Happy Number
 * A number is happy if repeatedly replacing it by the sum of squares of its digits
 * eventually reaches 1. Detect if it cycles forever.
 *
 * Approach: Use HashSet to detect cycles. If we see a number again, it's not happy.
 *
 * Time Complexity: O(log n) per step, bounded iterations
 * Space Complexity: O(log n) for the set
 *
 * Production Analogy: Like cycle detection in workflow engines.
 * If a state machine revisits a state, it's in an infinite loop.
 */
public class Problem14_HappyNumber {
    public boolean isHappy(int n) {
        Set<Integer> seen = new HashSet<>();
        while (n != 1 && seen.add(n)) {
            int sum = 0;
            while (n > 0) {
                int d = n % 10;
                sum += d * d;
                n /= 10;
            }
            n = sum;
        }
        return n == 1;
    }

    public static void main(String[] args) {
        Problem14_HappyNumber sol = new Problem14_HappyNumber();
        System.out.println(sol.isHappy(19)); // true
        System.out.println(sol.isHappy(2)); // false
        System.out.println(sol.isHappy(1)); // true
        System.out.println(sol.isHappy(7)); // true
    }
}
