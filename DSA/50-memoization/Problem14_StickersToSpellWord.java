import java.util.*;

public class Problem14_StickersToSpellWord {
    private Map<String, Integer> memo = new HashMap<>();

    public int minStickers(String[] stickers, String target) {
        int[][] counts = new int[stickers.length][26];
        for (int i = 0; i < stickers.length; i++)
            for (char c : stickers[i].toCharArray()) counts[i][c - 'a']++;
        memo.put("", 0);
        int result = helper(counts, target);
        return result == Integer.MAX_VALUE ? -1 : result;
    }

    private int helper(int[][] counts, String target) {
        if (memo.containsKey(target)) return memo.get(target);
        int[] tar = new int[26];
        for (char c : target.toCharArray()) tar[c - 'a']++;
        int min = Integer.MAX_VALUE;
        for (int[] sticker : counts) {
            if (sticker[target.charAt(0) - 'a'] == 0) continue;
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < 26; i++) {
                int remain = tar[i] - sticker[i];
                for (int j = 0; j < remain; j++) sb.append((char)('a' + i));
            }
            int sub = helper(counts, sb.toString());
            if (sub != Integer.MAX_VALUE) min = Math.min(min, sub + 1);
        }
        memo.put(target, min);
        return min;
    }

    public static void main(String[] args) {
        Problem14_StickersToSpellWord sol = new Problem14_StickersToSpellWord();
        System.out.println(sol.minStickers(new String[]{"with","example","science"}, "thehat")); // 3
    }
}
