/**
 * Problem 41: Reach a Number
 * Starting at 0 on number line, at step i move i units left or right.
 * Find minimum steps to reach target.
 *
 * Approach: Sum 1+2+...+k >= |target|, and (sum - target) must be even
 * (so we can flip one move's direction).
 * Time Complexity: O(sqrt(target))
 * Space Complexity: O(1)
 *
 * Production Analogy: Like finding minimum resource allocation steps where
 * each step has increasing capacity.
 */
public class Problem41_ReachANumber {

    public static int reachNumber(int target) {
        target = Math.abs(target);
        int step = 0, sum = 0;
        while (sum < target || (sum - target) % 2 != 0) {
            step++;
            sum += step;
        }
        return step;
    }

    public static void main(String[] args) {
        System.out.println(reachNumber(2));   // 3
        System.out.println(reachNumber(3));   // 2
        System.out.println(reachNumber(1));   // 1
        System.out.println(reachNumber(-2));  // 3
    }
}
