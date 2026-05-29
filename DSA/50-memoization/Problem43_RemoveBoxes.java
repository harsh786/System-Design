import java.util.*;

public class Problem43_RemoveBoxes {
    private Integer[][][] memo;

    public int removeBoxes(int[] boxes) {
        int n = boxes.length;
        memo = new Integer[n][n][n];
        return helper(boxes, 0, n - 1, 0);
    }

    private int helper(int[] boxes, int l, int r, int k) {
        if (l > r) return 0;
        if (memo[l][r][k] != null) return memo[l][r][k];
        int origL = l, origK = k;
        while (l + 1 <= r && boxes[l + 1] == boxes[l]) { l++; k++; }
        int result = (k + 1) * (k + 1) + helper(boxes, l + 1, r, 0);
        for (int i = l + 1; i <= r; i++) {
            if (boxes[i] == boxes[l]) {
                result = Math.max(result, helper(boxes, l + 1, i - 1, 0) + helper(boxes, i, r, k + 1));
            }
        }
        memo[origL][r][origK] = result;
        return result;
    }

    public static void main(String[] args) {
        Problem43_RemoveBoxes sol = new Problem43_RemoveBoxes();
        System.out.println(sol.removeBoxes(new int[]{1,3,2,2,2,3,4,3,1})); // 23
    }
}
