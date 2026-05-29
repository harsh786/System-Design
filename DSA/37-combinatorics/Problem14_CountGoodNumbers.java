public class Problem14_CountGoodNumbers {
    static final long MOD = 1_000_000_007;

    public int countGoodNumbers(long n) {
        long even = (n + 1) / 2, odd = n / 2;
        return (int)(power(5, even) * power(4, odd) % MOD);
    }

    private long power(long base, long exp) {
        long result = 1; base %= MOD;
        while (exp > 0) { if ((exp & 1) == 1) result = result * base % MOD; base = base * base % MOD; exp >>= 1; }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(new Problem14_CountGoodNumbers().countGoodNumbers(50));
    }
}
