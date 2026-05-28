import java.util.*;

/**
 * Problem 19: Matchsticks to Square (LeetCode 473)
 * 
 * Determine if matchsticks can form a perfect square (4 equal sides).
 * 
 * Search Tree:
 * - For each matchstick, try placing it in one of 4 sides
 * - 4^n branches at worst
 * 
 * Pruning Strategy:
 * - Sort descending: large sticks fail faster
 * - If a side exceeds target (sum/4), prune
 * - If sum % 4 != 0 or max stick > sum/4, return false immediately
 * - Skip duplicate sides: if sides[j] == sides[j-1] and j was just tried, skip
 * 
 * Time Complexity: O(4^n) worst case, much better with pruning
 * Space Complexity: O(n) recursion depth
 * 
 * Production Analogy:
 * - Load balancing: can we distribute n tasks across 4 servers with perfectly equal load?
 */
public class Problem19_MatchsticksToSquare {

    public boolean makesquare(int[] matchsticks) {
        int sum = 0;
        for (int m : matchsticks) sum += m;
        if (sum % 4 != 0) return false;
        int side = sum / 4;
        Arrays.sort(matchsticks);
        // Reverse to descending
        for (int i = 0, j = matchsticks.length - 1; i < j; i++, j--) {
            int tmp = matchsticks[i]; matchsticks[i] = matchsticks[j]; matchsticks[j] = tmp;
        }
        if (matchsticks[0] > side) return false;
        return backtrack(matchsticks, new int[4], 0, side);
    }

    private boolean backtrack(int[] matchsticks, int[] sides, int idx, int target) {
        if (idx == matchsticks.length) {
            return sides[0] == target && sides[1] == target && sides[2] == target;
        }
        for (int i = 0; i < 4; i++) {
            if (sides[i] + matchsticks[idx] > target) continue;
            if (i > 0 && sides[i] == sides[i - 1]) continue; // skip duplicate states
            sides[i] += matchsticks[idx];
            if (backtrack(matchsticks, sides, idx + 1, target)) return true;
            sides[i] -= matchsticks[idx];
        }
        return false;
    }

    public static void main(String[] args) {
        Problem19_MatchsticksToSquare sol = new Problem19_MatchsticksToSquare();

        System.out.println(sol.makesquare(new int[]{1,1,2,2,2}));   // true
        System.out.println(sol.makesquare(new int[]{3,3,3,3,4}));   // false
        System.out.println(sol.makesquare(new int[]{5,5,5,5,4,4,4,4,3,3,3,3})); // true
    }
}
