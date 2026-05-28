import java.util.*;

/**
 * Problem 26: 24 Game (LeetCode 679)
 * 
 * Given 4 cards with values 1-9, determine if you can get 24 using +,-,*,/ and parentheses.
 * 
 * Search Tree:
 * - Pick 2 numbers from remaining, apply one of 4 operations, put result back
 * - Repeat until 1 number remains; check if it equals 24
 * 
 * Pruning Strategy:
 * - Division by zero check
 * - Since + and * are commutative, can avoid some duplicates (optional)
 * - Use floating point with epsilon comparison
 * 
 * Time Complexity: O(4^3 * C(4,2) * C(3,2) * C(2,2)) = small constant
 * Space Complexity: O(1)
 * 
 * Production Analogy:
 * - Expression optimization: finding if a target metric can be derived from available data points.
 */
public class Problem26_24Game {

    private static final double EPS = 1e-6;

    public boolean judgePoint24(int[] cards) {
        List<Double> nums = new ArrayList<>();
        for (int c : cards) nums.add((double) c);
        return solve(nums);
    }

    private boolean solve(List<Double> nums) {
        if (nums.size() == 1) return Math.abs(nums.get(0) - 24) < EPS;
        for (int i = 0; i < nums.size(); i++) {
            for (int j = 0; j < nums.size(); j++) {
                if (i == j) continue;
                List<Double> next = new ArrayList<>();
                for (int k = 0; k < nums.size(); k++) if (k != i && k != j) next.add(nums.get(k));
                double a = nums.get(i), b = nums.get(j);
                double[] results = {a+b, a-b, a*b};
                for (double r : results) { next.add(r); if (solve(next)) return true; next.remove(next.size()-1); }
                if (Math.abs(b) > EPS) { next.add(a/b); if (solve(next)) return true; next.remove(next.size()-1); }
            }
        }
        return false;
    }

    public static void main(String[] args) {
        Problem26_24Game sol = new Problem26_24Game();

        System.out.println(sol.judgePoint24(new int[]{4,1,8,7})); // true (8-4)*(7-1)=24
        System.out.println(sol.judgePoint24(new int[]{1,2,1,2})); // false
        System.out.println(sol.judgePoint24(new int[]{1,5,5,5})); // true 5*(5-1/5)=24
    }
}
