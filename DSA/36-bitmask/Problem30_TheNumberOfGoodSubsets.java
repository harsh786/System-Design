import java.util.*;

public class Problem30_TheNumberOfGoodSubsets {
    public int numberOfGoodSubsets(int[] nums) {
        long MOD = 1_000_000_007;
        int[] primes = {2,3,5,7,11,13,17,19,23,29};
        int[] freq = new int[31];
        for (int n : nums) freq[n]++;
        long[] dp = new long[1 << 10];
        dp[0] = 1;
        for (int num = 2; num <= 30; num++) {
            if (freq[num] == 0) continue;
            int mask = 0; boolean valid = true; int tmp = num;
            for (int i = 0; i < 10; i++) {
                int cnt = 0;
                while (tmp % primes[i] == 0) { cnt++; tmp /= primes[i]; }
                if (cnt > 1) { valid = false; break; }
                if (cnt == 1) mask |= (1 << i);
            }
            if (!valid) continue;
            for (int state = (1 << 10) - 1; state >= 0; state--)
                if ((state & mask) == 0 && dp[state] > 0)
                    dp[state | mask] = (dp[state | mask] + dp[state] * freq[num]) % MOD;
        }
        long result = 0;
        for (int i = 1; i < (1 << 10); i++) result = (result + dp[i]) % MOD;
        // multiply by 2^count(1) since 1s can be included or not
        long pow = 1;
        for (int i = 0; i < freq[1]; i++) pow = pow * 2 % MOD;
        return (int)(result * pow % MOD);
    }

    public static void main(String[] args) {
        System.out.println(new Problem30_TheNumberOfGoodSubsets().numberOfGoodSubsets(new int[]{1,2,3,4}));
    }
}
