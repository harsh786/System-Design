/**
 * Problem 36: Happy Number
 * 
 * A number is happy if repeatedly summing squares of digits reaches 1.
 * 
 * Approach: Floyd's cycle detection on the digit-sum sequence.
 * Time: O(log n), Space: O(1)
 * 
 * Production Analogy: Like detecting infinite loops in a state machine -
 * if you revisit a state, you're in a cycle and will never reach the goal state.
 */
public class Problem36_HappyNumber {
    public static boolean isHappy(int n) {
        int slow = n, fast = n;
        do {
            slow = sumDigitSquares(slow);
            fast = sumDigitSquares(sumDigitSquares(fast));
        } while (slow != fast);
        return slow == 1;
    }

    private static int sumDigitSquares(int n) {
        int sum = 0;
        while (n > 0) { int d = n % 10; sum += d * d; n /= 10; }
        return sum;
    }

    public static void main(String[] args) {
        System.out.println(isHappy(19)); // true
        System.out.println(isHappy(2)); // false
        System.out.println(isHappy(1)); // true
    }
}
