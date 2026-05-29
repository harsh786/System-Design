public class Problem24_CountVowelsPermutation {
    public int countVowelPermutation(int n) {
        long MOD = 1_000_000_007;
        long a = 1, e = 1, i = 1, o = 1, u = 1;
        for (int k = 2; k <= n; k++) {
            long na = (e + i + u) % MOD, ne = (a + i) % MOD, ni = (e + o) % MOD, no = i, nu = (i + o) % MOD;
            a = na; e = ne; i = ni; o = no; u = nu;
        }
        return (int)((a + e + i + o + u) % MOD);
    }

    public static void main(String[] args) {
        System.out.println(new Problem24_CountVowelsPermutation().countVowelPermutation(5));
    }
}
