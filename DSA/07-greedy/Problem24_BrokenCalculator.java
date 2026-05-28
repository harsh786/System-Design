/**
 * Problem 24: Broken Calculator (LeetCode 991)
 *
 * Greedy Choice: Work backwards from target. If target is odd or larger, divide or add 1.
 * If target > startValue: if even, divide by 2; if odd, add 1 then divide.
 *
 * Time: O(log target), Space: O(1)
 *
 * Production Analogy: Reverse-engineering optimal scaling steps for auto-scaling down.
 */
public class Problem24_BrokenCalculator {
    
    public static int brokenCalc(int startValue, int target) {
        int ops = 0;
        while (target > startValue) {
            if (target % 2 == 1) target++;
            else target /= 2;
            ops++;
        }
        return ops + (startValue - target);
    }
    
    public static void main(String[] args) {
        System.out.println(brokenCalc(2, 3));    // 2
        System.out.println(brokenCalc(5, 8));    // 2
        System.out.println(brokenCalc(3, 10));   // 3
        System.out.println(brokenCalc(1024, 1)); // 1023
    }
}
