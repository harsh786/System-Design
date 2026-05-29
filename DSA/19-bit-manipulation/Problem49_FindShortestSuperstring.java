/**
 * Problem 49: Find the Shortest Superstring
 * Given array of strings, find shortest string containing all as substrings.
 * 
 * Approach: Precompute overlap between all pairs. TSP-like bitmask DP.
 * dp[mask][i] = max overlap achievable using strings in mask, ending with string i.
 * Time: O(2^n * n^2), Space: O(2^n * n)
 * 
 * Production Analogy: Minimum bandwidth encoding for transmitting multiple messages with overlap.
 */
import java.util.*;

public class Problem49_FindShortestSuperstring {
    public static String shortestSuperstring(String[] words) {
        int n = words.length;
        // overlap[i][j] = max overlap of words[i] suffix with words[j] prefix
        int[][] overlap = new int[n][n];
        for (int i = 0; i < n; i++)
            for (int j = 0; j < n; j++) if (i != j) {
                int max = Math.min(words[i].length(), words[j].length());
                for (int k = max; k >= 0; k--) {
                    if (words[i].endsWith(words[j].substring(0, k))) {
                        overlap[i][j] = k; break;
                    }
                }
            }
        
        // dp[mask][i] = max total overlap
        int[][] dp = new int[1 << n][n];
        int[][] parent = new int[1 << n][n];
        for (int[] row : parent) Arrays.fill(row, -1);
        
        for (int mask = 0; mask < (1 << n); mask++) {
            for (int i = 0; i < n; i++) {
                if ((mask & (1 << i)) == 0) continue;
                int prev = mask ^ (1 << i);
                if (prev == 0) continue;
                for (int j = 0; j < n; j++) {
                    if ((prev & (1 << j)) == 0) continue;
                    int val = dp[prev][j] + overlap[j][i];
                    if (val > dp[mask][i]) {
                        dp[mask][i] = val;
                        parent[mask][i] = j;
                    }
                }
            }
        }
        
        // Find best ending
        int full = (1 << n) - 1, last = 0;
        for (int i = 1; i < n; i++)
            if (dp[full][i] > dp[full][last]) last = i;
        
        // Reconstruct order
        int[] order = new int[n];
        int mask = full;
        for (int i = n - 1; i >= 0; i--) {
            order[i] = last;
            int prev = parent[mask][last];
            mask ^= (1 << last);
            last = prev;
        }
        
        // Build result
        StringBuilder sb = new StringBuilder(words[order[0]]);
        for (int i = 1; i < n; i++) {
            int ov = overlap[order[i-1]][order[i]];
            sb.append(words[order[i]].substring(ov));
        }
        return sb.toString();
    }

    public static void main(String[] args) {
        System.out.println(shortestSuperstring(new String[]{"alex","loves","leetcode"}));
        System.out.println(shortestSuperstring(new String[]{"catg","ctaagt","gcta","ttca","atgcatc"}));
    }
}
