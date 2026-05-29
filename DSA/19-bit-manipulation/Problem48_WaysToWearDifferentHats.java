/**
 * Problem 48: Number of Ways to Wear Different Hats to Each Other
 * n people, 40 hats. Each person has preferred hats. Assign distinct hats.
 * 
 * Approach: Bitmask over people (n <= 10). Iterate over hats.
 * dp[mask] = number of ways to assign hats to people in mask.
 * Time: O(40 * 2^n * n), Space: O(2^n)
 * 
 * Production Analogy: Assigning unique access tokens to users based on preferences.
 */
import java.util.*;

public class Problem48_WaysToWearDifferentHats {
    public static int numberWays(List<List<Integer>> hats) {
        int n = hats.size(), MOD = 1_000_000_007;
        // hatToPeople[h] = list of people who like hat h
        List<List<Integer>> hatToPeople = new ArrayList<>();
        for (int i = 0; i <= 40; i++) hatToPeople.add(new ArrayList<>());
        for (int i = 0; i < n; i++)
            for (int h : hats.get(i)) hatToPeople.get(h).add(i);
        
        int[] dp = new int[1 << n];
        dp[0] = 1;
        for (int h = 1; h <= 40; h++) {
            // Process in reverse to avoid using same hat twice
            for (int mask = (1 << n) - 1; mask >= 0; mask--) {
                if (dp[mask] == 0) continue;
                for (int person : hatToPeople.get(h)) {
                    if ((mask & (1 << person)) != 0) continue;
                    dp[mask | (1 << person)] = (int)((dp[mask | (1 << person)] + (long)dp[mask]) % MOD);
                }
            }
        }
        return dp[(1 << n) - 1];
    }

    public static void main(String[] args) {
        System.out.println(numberWays(List.of(List.of(3,4), List.of(4,5), List.of(5)))); // 1
        System.out.println(numberWays(List.of(List.of(3,5,1), List.of(3,5)))); // 4
    }
}
