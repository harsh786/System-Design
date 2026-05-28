/**
 * Problem 45: Split Array into Consecutive Subsequences (LeetCode 659)
 *
 * Greedy Choice: For each number, extend an existing subsequence if possible;
 * otherwise start a new one (needs next two numbers available).
 *
 * Time: O(n), Space: O(n)
 *
 * Production Analogy: Splitting event streams into valid consecutive sequences for processing.
 */
import java.util.*;
public class Problem45_SplitArrayConsecutiveSubsequences {
    
    public static boolean isPossible(int[] nums) {
        Map<Integer, Integer> freq = new HashMap<>(), tails = new HashMap<>();
        for (int n : nums) freq.merge(n, 1, Integer::sum);
        for (int n : nums) {
            if (freq.getOrDefault(n, 0) == 0) continue;
            if (tails.getOrDefault(n, 0) > 0) {
                tails.merge(n, -1, Integer::sum);
                tails.merge(n + 1, 1, Integer::sum);
            } else if (freq.getOrDefault(n+1, 0) > 0 && freq.getOrDefault(n+2, 0) > 0) {
                freq.merge(n+1, -1, Integer::sum);
                freq.merge(n+2, -1, Integer::sum);
                tails.merge(n+3, 1, Integer::sum);
            } else return false;
            freq.merge(n, -1, Integer::sum);
        }
        return true;
    }
    
    public static void main(String[] args) {
        System.out.println(isPossible(new int[]{1,2,3,3,4,5}));     // true
        System.out.println(isPossible(new int[]{1,2,3,3,4,4,5,5})); // true
        System.out.println(isPossible(new int[]{1,2,3,4,4,5}));     // false
    }
}
