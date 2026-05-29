import java.util.Arrays;

public class Problem26_FindTheShortestSuperstring {
    public String shortestSuperstring(String[] words) {
        int n = words.length;
        int[][] overlap = new int[n][n];
        for (int i = 0; i < n; i++) for (int j = 0; j < n; j++) if (i != j) {
            int max = Math.min(words[i].length(), words[j].length());
            for (int k = max; k >= 1; k--)
                if (words[i].endsWith(words[j].substring(0, k))) { overlap[i][j] = k; break; }
        }
        int[][] dp = new int[1 << n][n];
        int[][] parent = new int[1 << n][n];
        for (int[] row : parent) Arrays.fill(row, -1);
        for (int mask = 0; mask < (1 << n); mask++) for (int last = 0; last < n; last++) {
            if ((mask & (1 << last)) == 0) continue;
            int prev = mask ^ (1 << last);
            if (prev == 0) continue;
            for (int p = 0; p < n; p++) {
                if ((prev & (1 << p)) == 0) continue;
                int val = dp[prev][p] + overlap[p][last];
                if (val > dp[mask][last]) { dp[mask][last] = val; parent[mask][last] = p; }
            }
        }
        int full = (1 << n) - 1, last = 0;
        for (int i = 1; i < n; i++) if (dp[full][i] > dp[full][last]) last = i;
        int[] order = new int[n]; int mask = full;
        for (int i = n - 1; i >= 0; i--) { order[i] = last; int p = parent[mask][last]; mask ^= (1 << last); last = p; }
        StringBuilder sb = new StringBuilder(words[order[0]]);
        for (int i = 1; i < n; i++) sb.append(words[order[i]].substring(overlap[order[i-1]][order[i]]));
        return sb.toString();
    }

    public static void main(String[] args) {
        System.out.println(new Problem26_FindTheShortestSuperstring().shortestSuperstring(new String[]{"alex","loves","leetcode"}));
    }
}
