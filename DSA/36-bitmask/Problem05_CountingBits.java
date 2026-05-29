import java.util.Arrays;

public class Problem05_CountingBits {
    public int[] countBits(int n) {
        int[] dp = new int[n + 1];
        for (int i = 1; i <= n; i++) dp[i] = dp[i >> 1] + (i & 1);
        return dp;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(new Problem05_CountingBits().countBits(5)));
    }
}
