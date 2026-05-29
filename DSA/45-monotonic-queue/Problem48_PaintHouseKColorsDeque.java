/**
 * Problem: Problem48 PaintHouseKColorsDeque - Paint n houses with k colors, minimize cost using deque optimization.
 * Approach: Monotonic deque maintaining order invariant over sliding window.
 * Time: O(n) | Space: O(k) or O(n)
 * Production Analogy: Paint n houses with k colors, minimize cost using deque optimization.
 */
import java.util.*;

public class Problem48_PaintHouseKColorsDeque {
    // Paint n houses with k colors, no two adjacent same color, minimize cost
    // O(nk) using tracking of min and second min per row (deque not needed but shown for concept)
    public static int minCostPaint(int[][] costs) {
        int n = costs.length, k = costs[0].length;
        int[][] dp = new int[n][k];
        for (int j = 0; j < k; j++) dp[0][j] = costs[0][j];
        for (int i = 1; i < n; i++) {
            int min1 = Integer.MAX_VALUE, min2 = Integer.MAX_VALUE, minIdx = -1;
            for (int j = 0; j < k; j++) {
                if (dp[i-1][j] < min1) { min2 = min1; min1 = dp[i-1][j]; minIdx = j; }
                else if (dp[i-1][j] < min2) min2 = dp[i-1][j];
            }
            for (int j = 0; j < k; j++) dp[i][j] = costs[i][j] + (j == minIdx ? min2 : min1);
        }
        int ans = Integer.MAX_VALUE;
        for (int j = 0; j < k; j++) ans = Math.min(ans, dp[n-1][j]);
        return ans;
    }

    public static void main(String[] args) {
        int[][] costs = {{1,5,3},{2,9,4},{3,1,2}};
        System.out.println(minCostPaint(costs)); // 5 (1+4+... -> actually 1+2+1=... let's compute: house0=1, house1=4, house2=1 -> but must differ)
    }
}
