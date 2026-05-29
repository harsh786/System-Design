public class Problem43_NcrModPLucasTheorem {
    // Lucas theorem: C(n,r) mod p for prime p
    public long nCrModP(long n, long r, long p) {
        if (r == 0) return 1;
        return nCrModP(n / p, r / p, p) * nCrSmall((int)(n % p), (int)(r % p), p) % p;
    }

    private long nCrSmall(int n, int r, long p) {
        if (r > n) return 0;
        long num = 1, den = 1;
        for (int i = 0; i < r; i++) { num = num * (n - i) % p; den = den * (i + 1) % p; }
        return num * modPow(den, p - 2, p) % p;
    }

    private long modPow(long base, long exp, long mod) {
        long r = 1; base %= mod;
        while (exp > 0) { if ((exp & 1) == 1) r = r * base % mod; base = base * base % mod; exp >>= 1; }
        return r;
    }

    public static void main(String[] args) {
        System.out.println(new Problem43_NcrModPLucasTheorem().nCrModP(1000, 500, 13));
    }
}
