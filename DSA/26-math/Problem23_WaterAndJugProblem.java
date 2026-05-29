/**
 * Problem 23: Water and Jug Problem (GCD)
 * Can you measure exactly targetCapacity using two jugs of capacities x and y?
 *
 * Approach: By Bezout's identity, achievable iff target % gcd(x,y) == 0 and target <= x+y.
 * Time Complexity: O(log(min(x,y))) for GCD
 * Space Complexity: O(1)
 *
 * Production Analogy: Like determining if a specific bandwidth allocation is
 * achievable given fixed channel widths (must be multiple of GCD).
 */
public class Problem23_WaterAndJugProblem {

    public static boolean canMeasureWater(int x, int y, int target) {
        if (x + y < target) return false;
        if (x == 0 || y == 0) return target == 0 || x + y == target;
        return target % gcd(x, y) == 0;
    }

    private static int gcd(int a, int b) {
        return b == 0 ? a : gcd(b, a % b);
    }

    public static void main(String[] args) {
        System.out.println(canMeasureWater(3, 5, 4));  // true
        System.out.println(canMeasureWater(2, 6, 5));  // false
        System.out.println(canMeasureWater(1, 2, 3));  // true
        System.out.println(canMeasureWater(0, 0, 0));  // true
    }
}
