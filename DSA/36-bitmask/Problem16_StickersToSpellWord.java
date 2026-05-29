import java.util.*;

public class Problem16_StickersToSpellWord {
    public int minStickers(String[] stickers, String target) {
        int n = target.length();
        int[] dp = new int[1 << n];
        Arrays.fill(dp, Integer.MAX_VALUE);
        dp[0] = 0;
        for (int mask = 0; mask < (1 << n); mask++) {
            if (dp[mask] == Integer.MAX_VALUE) continue;
            for (String sticker : stickers) {
                int cur = mask;
                int[] freq = new int[26];
                for (char c : sticker.toCharArray()) freq[c - 'a']++;
                for (int i = 0; i < n; i++) {
                    if ((cur & (1 << i)) != 0) continue;
                    if (freq[target.charAt(i) - 'a'] > 0) { cur |= (1 << i); freq[target.charAt(i) - 'a']--; }
                }
                dp[cur] = Math.min(dp[cur], dp[mask] + 1);
            }
        }
        return dp[(1 << n) - 1] == Integer.MAX_VALUE ? -1 : dp[(1 << n) - 1];
    }

    public static void main(String[] args) {
        System.out.println(new Problem16_StickersToSpellWord().minStickers(new String[]{"with","example","science"}, "thehat"));
    }
}
