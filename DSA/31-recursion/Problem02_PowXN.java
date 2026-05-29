public class Problem02_PowXN {
    public static double myPow(double x, int n) {
        long N = n;
        if (N < 0) { x = 1 / x; N = -N; }
        return power(x, N);
    }
    static double power(double x, long n) {
        if (n == 0) return 1;
        double half = power(x, n / 2);
        return n % 2 == 0 ? half * half : half * half * x;
    }
    public static void main(String[] args) {
        System.out.println(myPow(2.0, 10)); // 1024.0
        System.out.println(myPow(2.0, -2)); // 0.25
    }
}
