/**
 * Problem 46: GCD and LCM
 * Compute Greatest Common Divisor and Least Common Multiple.
 *
 * Approach: Euclidean algorithm for GCD. LCM = a * b / GCD(a, b).
 * Time Complexity: O(log(min(a,b)))
 * Space Complexity: O(1) iterative
 *
 * Production Analogy: Like computing common intervals for synchronizing
 * periodic tasks in real-time systems (LCM of periods = hyperperiod).
 */
public class Problem46_GCDAndLCM {

    public static int gcd(int a, int b) {
        while (b != 0) {
            int temp = b;
            b = a % b;
            a = temp;
        }
        return a;
    }

    public static long lcm(int a, int b) {
        return (long) a / gcd(a, b) * b;
    }

    // GCD of array
    public static int gcdArray(int[] nums) {
        int result = nums[0];
        for (int i = 1; i < nums.length; i++) {
            result = gcd(result, nums[i]);
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(gcd(12, 8));     // 4
        System.out.println(gcd(17, 5));     // 1
        System.out.println(lcm(12, 8));     // 24
        System.out.println(lcm(7, 3));      // 21
        System.out.println(gcdArray(new int[]{12, 18, 24})); // 6
        System.out.println(gcd(0, 5));      // 5
    }
}
