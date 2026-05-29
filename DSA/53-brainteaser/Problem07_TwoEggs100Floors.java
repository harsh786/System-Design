public class Problem07_TwoEggs100Floors {
    // Classic: minimize worst case with 2 eggs and 100 floors
    // Optimal: drop at intervals that decrease by 1: x + (x-1) + ... + 1 >= 100 => x=14
    static int solve(int floors) {
        int x = 1;
        while (x * (x + 1) / 2 < floors) x++;
        return x;
    }
    
    // DP verification
    static int dpSolve(int eggs, int floors) {
        int[][] dp = new int[eggs + 1][floors + 1];
        for (int f = 1; f <= floors; f++) dp[1][f] = f;
        for (int e = 2; e <= eggs; e++) {
            for (int f = 1; f <= floors; f++) {
                dp[e][f] = Integer.MAX_VALUE;
                for (int k = 1; k <= f; k++)
                    dp[e][f] = Math.min(dp[e][f], 1 + Math.max(dp[e-1][k-1], dp[e][f-k]));
            }
        }
        return dp[eggs][floors];
    }
    
    public static void main(String[] args) {
        System.out.println("Formula: " + solve(100)); // 14
        System.out.println("DP: " + dpSolve(2, 100)); // 14
    }
}
