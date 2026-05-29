public class Problem35_CountAnagrams {
    static final long MOD = 1_000_000_007;

    public int countAnagrams(String s) {
        String[] words = s.split(" ");
        long result = 1;
        for (String w : words) {
            int[] freq = new int[26];
            for (char c : w.toCharArray()) freq[c - 'a']++;
            long num = factorial(w.length());
            long den = 1;
            for (int f : freq) if (f > 1) den = den * factorial(f) % MOD;
            result = result * num % MOD * modInverse(den) % MOD;
        }
        return (int) result;
    }

    private long factorial(int n) { long r = 1; for (int i = 2; i <= n; i++) r = r * i % MOD; return r; }
    private long modInverse(long a) { return power(a, MOD - 2); }
    private long power(long base, long exp) { long r = 1; base %= MOD; while (exp > 0) { if ((exp & 1) == 1) r = r * base % MOD; base = base * base % MOD; exp >>= 1; } return r; }

    public static void main(String[] args) {
        System.out.println(new Problem35_CountAnagrams().countAnagrams("too hot"));
    }
}
