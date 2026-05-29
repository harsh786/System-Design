/**
 * Problem 49: Euler's Totient Function
 * Compute phi(n) = count of integers in [1, n] coprime with n.
 *
 * Approach: n * product((1 - 1/p)) for all prime factors p of n.
 * Time Complexity: O(sqrt(n))
 * Space Complexity: O(1)
 *
 * Production Analogy: Like computing the number of valid keys in RSA
 * (phi(n) = (p-1)(q-1) determines the key space).
 */
public class Problem49_EulersTotientFunction {

    public static long eulerTotient(long n) {
        long result = n;
        for (long p = 2; p * p <= n; p++) {
            if (n % p == 0) {
                while (n % p == 0) n /= p;
                result -= result / p;
            }
        }
        if (n > 1) result -= result / n;
        return result;
    }

    // Compute totient for all numbers up to n (sieve approach)
    public static int[] totientSieve(int n) {
        int[] phi = new int[n + 1];
        for (int i = 0; i <= n; i++) phi[i] = i;
        for (int i = 2; i <= n; i++) {
            if (phi[i] == i) { // i is prime
                for (int j = i; j <= n; j += i) {
                    phi[j] -= phi[j] / i;
                }
            }
        }
        return phi;
    }

    public static void main(String[] args) {
        System.out.println(eulerTotient(1));    // 1
        System.out.println(eulerTotient(10));   // 4 (1,3,7,9)
        System.out.println(eulerTotient(12));   // 4 (1,5,7,11)
        System.out.println(eulerTotient(7));    // 6 (prime)
        System.out.println(eulerTotient(36));   // 12

        int[] sieve = totientSieve(10);
        for (int i = 1; i <= 10; i++) System.out.print(sieve[i] + " ");
        // 1 1 2 2 4 2 6 4 6 4
        System.out.println();
    }
}
