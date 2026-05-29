public class Problem20_InclusionExclusionDivisibleCounts {
    // Count numbers in [1,n] divisible by at least one element in primes[]
    public int countDivisible(int n, int[] primes) {
        int count = 0;
        for (int mask = 1; mask < (1 << primes.length); mask++) {
            long lcm = 1; int bits = 0;
            for (int i = 0; i < primes.length; i++) {
                if ((mask & (1 << i)) != 0) { lcm = lcm / gcd(lcm, primes[i]) * primes[i]; bits++; }
            }
            count += (bits % 2 == 1 ? 1 : -1) * (n / lcm);
        }
        return count;
    }

    private long gcd(long a, long b) { return b == 0 ? a : gcd(b, a % b); }

    public static void main(String[] args) {
        System.out.println(new Problem20_InclusionExclusionDivisibleCounts().countDivisible(30, new int[]{2, 3, 5}));
    }
}
