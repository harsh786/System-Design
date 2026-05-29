/**
 * Problem 50: Maximum Compatibility Score Sum
 * m students, m mentors, each with n answers. Assign students to mentors 1:1 maximizing total score.
 * 
 * Approach: Bitmask DP over mentor assignments. dp[mask] = max score assigning first popcount(mask)
 * students to mentors in mask.
 * Time: O(2^m * m), Space: O(2^m)
 * 
 * Production Analogy: Optimal matching of engineers to teams based on skill compatibility.
 */
import java.util.*;

public class Problem50_MaxCompatibilityScoreSum {
    public static int maxCompatibilitySum(int[][] students, int[][] mentors) {
        int m = students.length, n = students[0].length;
        // Precompute compatibility scores
        int[][] score = new int[m][m];
        for (int i = 0; i < m; i++)
            for (int j = 0; j < m; j++)
                for (int k = 0; k < n; k++)
                    if (students[i][k] == mentors[j][k]) score[i][j]++;
        
        int[] dp = new int[1 << m];
        Arrays.fill(dp, -1);
        dp[0] = 0;
        for (int mask = 0; mask < (1 << m); mask++) {
            if (dp[mask] == -1) continue;
            int student = Integer.bitCount(mask); // next student to assign
            if (student >= m) continue;
            for (int j = 0; j < m; j++) {
                if ((mask & (1 << j)) != 0) continue;
                int newMask = mask | (1 << j);
                dp[newMask] = Math.max(dp[newMask], dp[mask] + score[student][j]);
            }
        }
        return dp[(1 << m) - 1];
    }

    public static void main(String[] args) {
        int[][] students = {{1,1,0},{1,0,1},{0,0,1}};
        int[][] mentors = {{1,0,0},{0,0,1},{1,1,0}};
        System.out.println(maxCompatibilitySum(students, mentors)); // 8

        students = new int[][]{{0,0},{0,0},{0,0}};
        mentors = new int[][]{{1,1},{1,1},{1,1}};
        System.out.println(maxCompatibilitySum(students, mentors)); // 0
    }
}
