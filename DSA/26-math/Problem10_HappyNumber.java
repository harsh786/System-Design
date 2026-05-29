/**
 * Problem 10: Happy Number
 * A number is happy if repeatedly summing squares of digits eventually reaches 1.
 *
 * Approach: Floyd's cycle detection (fast/slow pointer on digit-square sequence).
 * Time Complexity: O(log n) per step, cycle length bounded
 * Space Complexity: O(1)
 *
 * Production Analogy: Like detecting infinite loops in state machines or
 * cycle detection in linked data structures.
 */
public class Problem10_HappyNumber {

    private static int getNext(int n) {
        int sum = 0;
        while (n > 0) {
            int d = n % 10;
            sum += d * d;
            n /= 10;
        }
        return sum;
    }

    public static boolean isHappy(int n) {
        int slow = n, fast = getNext(n);
        while (fast != 1 && slow != fast) {
            slow = getNext(slow);
            fast = getNext(getNext(fast));
        }
        return fast == 1;
    }

    public static void main(String[] args) {
        System.out.println(isHappy(19));  // true
        System.out.println(isHappy(2));   // false
        System.out.println(isHappy(1));   // true
        System.out.println(isHappy(7));   // true
    }
}
