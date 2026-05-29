import java.util.*;

public class Problem07_New21Game {
    public double new21Game(int n, int k, int maxPts) {
        if (k == 0 || n >= k + maxPts) return 1.0;
        double[] dp = new double[n + 1];
        dp[0] = 1.0;
        double windowSum = 1.0, prob = 0.0;
        for (int i = 1; i <= n; i++) {
            dp[i] = windowSum / maxPts;
            if (i < k) windowSum += dp[i];
            if (i - maxPts >= 0 && i - maxPts < k) windowSum -= dp[i - maxPts];
            if (i >= k) prob += dp[i];
        }
        return prob;
    }

    public static void main(String[] args) {
        Problem07_New21Game sol = new Problem07_New21Game();
        System.out.println(sol.new21Game(21, 17, 10)); // 0.73278
    }
}
