public class Problem14_New21Game {
    // LC 837: Draw cards 1..maxPts until >= k, probability score <= n
    static double new21Game(int n, int k, int maxPts) {
        if (k == 0 || n >= k + maxPts - 1) return 1.0;
        double[] dp = new double[n + 1];
        dp[0] = 1.0;
        double windowSum = 1.0, result = 0.0;
        for (int i = 1; i <= n; i++) {
            dp[i] = windowSum / maxPts;
            if (i < k) windowSum += dp[i];
            else result += dp[i];
            if (i >= maxPts) windowSum -= dp[i - maxPts];
        }
        return result;
    }
    
    public static void main(String[] args) {
        System.out.printf("new21Game(21,17,10) = %.5f%n", new21Game(21, 17, 10));
    }
}
