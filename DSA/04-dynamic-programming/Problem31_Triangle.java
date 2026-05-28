/**
 * Problem 31: Triangle
 * 
 * Find minimum path sum from top to bottom. Each step move to adjacent numbers below.
 * 
 * Bottom-up: dp[j] = min(dp[j], dp[j+1]) + triangle[i][j]
 * Time: O(n^2), Space: O(n)
 */
import java.util.*;

public class Problem31_Triangle {

    public static int minimumTotal(List<List<Integer>> triangle) {
        int n = triangle.size();
        int[] dp = new int[n + 1];
        for (int i = n - 1; i >= 0; i--) {
            for (int j = 0; j <= i; j++) {
                dp[j] = triangle.get(i).get(j) + Math.min(dp[j], dp[j + 1]);
            }
        }
        return dp[0];
    }

    public static void main(String[] args) {
        System.out.println("=== Triangle ===");
        List<List<Integer>> tri = Arrays.asList(
            Arrays.asList(2),
            Arrays.asList(3,4),
            Arrays.asList(6,5,7),
            Arrays.asList(4,1,8,3)
        );
        System.out.println(minimumTotal(tri)); // 11
    }
}
