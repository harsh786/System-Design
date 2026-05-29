import java.util.*;

public class Problem08_SoupServings {
    private Map<Long, Double> memo = new HashMap<>();

    public double soupServings(int n) {
        if (n > 4800) return 1.0;
        return solve((n + 24) / 25, (n + 24) / 25);
    }

    private double solve(int a, int b) {
        if (a <= 0 && b <= 0) return 0.5;
        if (a <= 0) return 1.0;
        if (b <= 0) return 0.0;
        long key = (long)a * 200 + b;
        if (memo.containsKey(key)) return memo.get(key);
        double res = 0.25 * (solve(a-4,b) + solve(a-3,b-1) + solve(a-2,b-2) + solve(a-1,b-3));
        memo.put(key, res);
        return res;
    }

    public static void main(String[] args) {
        Problem08_SoupServings sol = new Problem08_SoupServings();
        System.out.println(sol.soupServings(50));
    }
}
