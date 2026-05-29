public class Problem44_CatalanNumber {
    static final long MOD = 1_000_000_007;

    public long catalan(int n) {
        // C(n) = C(2n, n) / (n+1)
        long num = 1;
        for (int i = 0; i < n; i++) num = num * (2 * n - i) % MOD * modInverse(i + 1) % MOD;
        return num * modInverse(n + 1) % MOD;
    }

    private long modInverse(long a) { return modPow(a, MOD - 2); }
    private long modPow(long base, long exp) { long r = 1; base %= MOD; while (exp > 0) { if ((exp & 1) == 1) r = r * base % MOD; base = base * base % MOD; exp >>= 1; } return r; }

    public static void main(String[] args) {
        Problem44_CatalanNumber sol = new Problem44_CatalanNumber();
        for (int i = 0; i <= 10; i++) System.out.print(sol.catalan(i) + " ");
    }
}
