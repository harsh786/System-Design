/**
 * Problem 40: Stickers to Spell Word
 * Given stickers (strings), spell target using minimum stickers. Each sticker has unlimited copies.
 * 
 * Approach: Bitmask DP where mask represents which chars of target are covered.
 * Time: O(2^n * m * t) where n=target.length, m=stickers, t=sticker length. Space: O(2^n)
 * 
 * Production Analogy: Minimum resource bundles needed to satisfy all feature requirements.
 */
import java.util.*;

public class Problem40_StickersToSpellWord {
    public static int minStickers(String[] stickers, String target) {
        int n = target.length();
        int[] dp = new int[1 << n];
        Arrays.fill(dp, Integer.MAX_VALUE);
        dp[0] = 0;
        for (int mask = 0; mask < (1 << n); mask++) {
            if (dp[mask] == Integer.MAX_VALUE) continue;
            for (String sticker : stickers) {
                int newMask = mask;
                int[] freq = new int[26];
                for (char c : sticker.toCharArray()) freq[c - 'a']++;
                for (int i = 0; i < n; i++) {
                    if ((newMask & (1 << i)) != 0) continue;
                    int c = target.charAt(i) - 'a';
                    if (freq[c] > 0) {
                        newMask |= (1 << i);
                        freq[c]--;
                    }
                }
                dp[newMask] = Math.min(dp[newMask], dp[mask] + 1);
            }
        }
        return dp[(1 << n) - 1] == Integer.MAX_VALUE ? -1 : dp[(1 << n) - 1];
    }

    public static void main(String[] args) {
        System.out.println(minStickers(new String[]{"with","example","science"}, "thehat")); // 3
        System.out.println(minStickers(new String[]{"notice","possible"}, "basicbasic")); // -1
    }
}
