public class Problem01_ClimbingStairs {
    public static int climbStairs(int n) {
        if (n <= 2) return n;
        return climbStairsMemo(n, new int[n + 1]);
    }
    static int climbStairsMemo(int n, int[] memo) {
        if (n <= 2) return n;
        if (memo[n] != 0) return memo[n];
        return memo[n] = climbStairsMemo(n - 1, memo) + climbStairsMemo(n - 2, memo);
    }
    public static void main(String[] args) {
        System.out.println(climbStairs(5)); // 8
    }
}
