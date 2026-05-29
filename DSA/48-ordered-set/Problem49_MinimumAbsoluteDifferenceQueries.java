import java.util.*;

public class Problem49_MinimumAbsoluteDifferenceQueries {
    // LC 1906: Min absolute diff between any two elements in subarray [l, r]
    // Values in [1, 100], use prefix counts
    public static int[] minDifference(int[] nums, int[][] queries) {
        int n = nums.length;
        int[][] prefix = new int[n + 1][101];
        for (int i = 0; i < n; i++) {
            System.arraycopy(prefix[i], 0, prefix[i + 1], 0, 101);
            prefix[i + 1][nums[i]]++;
        }
        int[] ans = new int[queries.length];
        for (int q = 0; q < queries.length; q++) {
            int l = queries[q][0], r = queries[q][1];
            int minDiff = Integer.MAX_VALUE, prev = -1;
            for (int v = 1; v <= 100; v++) {
                if (prefix[r + 1][v] - prefix[l][v] > 0) {
                    if (prev != -1) minDiff = Math.min(minDiff, v - prev);
                    prev = v;
                }
            }
            ans[q] = minDiff == Integer.MAX_VALUE ? -1 : minDiff;
        }
        return ans;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(minDifference(
            new int[]{1,3,4,8}, new int[][]{{0,1},{1,2},{2,3},{0,3}})));
        // [2,1,4,1]
    }
}
