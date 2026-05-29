import java.util.*;

public class Problem21_FibonacciMemoized {
    private Map<Integer, Long> memo = new HashMap<>();

    public long fib(int n) {
        if (n <= 1) return n;
        if (memo.containsKey(n)) return memo.get(n);
        long result = fib(n - 1) + fib(n - 2);
        memo.put(n, result);
        return result;
    }

    public static void main(String[] args) {
        Problem21_FibonacciMemoized sol = new Problem21_FibonacciMemoized();
        System.out.println("Fib(10): " + sol.fib(10)); // 55
        System.out.println("Fib(50): " + sol.fib(50)); // 12586269025
    }
}
