import java.util.*;

public class Problem01_ClimbingStairs {
    private Map<Integer, Integer> memo = new HashMap<>();

    public int climbStairs(int n) {
        if (n <= 2) return n;
        if (memo.containsKey(n)) return memo.get(n);
        int result = climbStairs(n - 1) + climbStairs(n - 2);
        memo.put(n, result);
        return result;
    }

    public static void main(String[] args) {
        Problem01_ClimbingStairs sol = new Problem01_ClimbingStairs();
        System.out.println("Climbing Stairs (n=5): " + sol.climbStairs(5)); // 8
        System.out.println("Climbing Stairs (n=10): " + sol.climbStairs(10)); // 89
    }
}
