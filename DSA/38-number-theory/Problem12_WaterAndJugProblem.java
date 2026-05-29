package numbertheory;

/**
 * Problem 12: Water and Jug Problem (LeetCode 365)
 * 
 * Approach: By Bezout's identity, target is achievable iff target % gcd(x,y) == 0 and target <= x+y.
 * 
 * Time Complexity: O(log(min(x,y)))
 * Space Complexity: O(1)
 */
public class Problem12_WaterAndJugProblem {
    
    public boolean canMeasureWater(int x, int y, int target) {
        if (x + y < target) return false;
        if (x == 0 || y == 0) return target == 0 || x + y == target;
        return target % gcd(x, y) == 0;
    }
    
    private int gcd(int a, int b) { return b == 0 ? a : gcd(b, a % b); }
    
    public static void main(String[] args) {
        Problem12_WaterAndJugProblem sol = new Problem12_WaterAndJugProblem();
        System.out.println(sol.canMeasureWater(3, 5, 4)); // true
        System.out.println(sol.canMeasureWater(2, 6, 5)); // false
    }
}
