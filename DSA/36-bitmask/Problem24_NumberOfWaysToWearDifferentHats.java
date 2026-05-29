import java.util.*;

public class Problem24_NumberOfWaysToWearDifferentHats {
    public int numberWays(List<List<Integer>> hats) {
        int n = hats.size();
        long MOD = 1_000_000_007;
        List<List<Integer>> hatToPeople = new ArrayList<>();
        for (int i = 0; i <= 40; i++) hatToPeople.add(new ArrayList<>());
        for (int i = 0; i < n; i++) for (int h : hats.get(i)) hatToPeople.get(h).add(i);
        long[] dp = new long[1 << n];
        dp[0] = 1;
        for (int h = 1; h <= 40; h++) {
            for (int mask = (1 << n) - 1; mask >= 0; mask--) {
                if (dp[mask] == 0) continue;
                for (int p : hatToPeople.get(h)) {
                    if ((mask & (1 << p)) != 0) continue;
                    dp[mask | (1 << p)] = (dp[mask | (1 << p)] + dp[mask]) % MOD;
                }
            }
        }
        return (int) dp[(1 << n) - 1];
    }

    public static void main(String[] args) {
        System.out.println(new Problem24_NumberOfWaysToWearDifferentHats().numberWays(
            Arrays.asList(Arrays.asList(3,4), Arrays.asList(4,5), Arrays.asList(5))));
    }
}
