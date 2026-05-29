import java.util.*;

public class Problem17_RemoveBoxesGame {
    // 546. Remove Boxes: Remove boxes to maximize points. Removing k consecutive same-color = k*k points.
    
    int[][][] dp;
    
    public int removeBoxes(int[] boxes) {
        int n = boxes.length;
        dp = new int[n][n][n];
        return solve(boxes, 0, n - 1, 0);
    }
    
    private int solve(int[] boxes, int l, int r, int k) {
        if (l > r) return 0;
        if (dp[l][r][k] != 0) return dp[l][r][k];
        // Optimization: merge consecutive same colors on the left
        int origL = l, origK = k;
        while (l + 1 <= r && boxes[l+1] == boxes[l]) { l++; k++; }
        int res = (k + 1) * (k + 1) + solve(boxes, l + 1, r, 0);
        for (int m = l + 1; m <= r; m++) {
            if (boxes[m] == boxes[l]) {
                res = Math.max(res, solve(boxes, l + 1, m - 1, 0) + solve(boxes, m, r, k + 1));
            }
        }
        dp[origL][r][origK] = res;
        return res;
    }
    
    public static void main(String[] args) {
        Problem17_RemoveBoxesGame sol = new Problem17_RemoveBoxesGame();
        System.out.println(sol.removeBoxes(new int[]{1,3,2,2,2,3,4,3,1})); // 23
    }
}
