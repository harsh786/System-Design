public class Problem42_BinomialCoefficientComputation {
    public long binomial(int n, int r) {
        if (r > n - r) r = n - r;
        long result = 1;
        for (int i = 0; i < r; i++) result = result * (n - i) / (i + 1);
        return result;
    }

    // DP version for modular arithmetic
    public long binomialMod(int n, int r, long mod) {
        long[][] C = new long[n + 1][r + 1];
        for (int i = 0; i <= n; i++) { C[i][0] = 1; for (int j = 1; j <= Math.min(i, r); j++) C[i][j] = (C[i-1][j-1] + C[i-1][j]) % mod; }
        return C[n][r];
    }

    public static void main(String[] args) {
        Problem42_BinomialCoefficientComputation sol = new Problem42_BinomialCoefficientComputation();
        System.out.println(sol.binomial(10, 3)); // 120
        System.out.println(sol.binomialMod(10, 3, 1_000_000_007)); // 120
    }
}
