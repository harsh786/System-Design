import java.util.*;

public class Problem49_SoupServings {
    private Map<String, Double> memo = new HashMap<>();

    public double soupServings(int n) {
        if (n > 4800) return 1.0;
        n = (int) Math.ceil(n / 25.0);
        return helper(n, n);
    }

    private double helper(int a, int b) {
        if (a <= 0 && b <= 0) return 0.5;
        if (a <= 0) return 1.0;
        if (b <= 0) return 0.0;
        String key = a + "," + b;
        if (memo.containsKey(key)) return memo.get(key);
        double result = 0.25 * (helper(a-4,b) + helper(a-3,b-1) + helper(a-2,b-2) + helper(a-1,b-3));
        memo.put(key, result);
        return result;
    }

    public static void main(String[] args) {
        Problem49_SoupServings sol = new Problem49_SoupServings();
        System.out.printf("Soup Servings n=50: %.5f%n", sol.soupServings(50)); // 0.625
    }
}
