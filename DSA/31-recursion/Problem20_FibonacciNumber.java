public class Problem20_FibonacciNumber {
    public static int fib(int n) {
        if (n <= 1) return n;
        return fibMemo(n, new int[n + 1]);
    }
    static int fibMemo(int n, int[] memo) {
        if (n <= 1) return n;
        if (memo[n] != 0) return memo[n];
        return memo[n] = fibMemo(n - 1, memo) + fibMemo(n - 2, memo);
    }
    public static void main(String[] args) {
        System.out.println(fib(10)); // 55
    }
}
