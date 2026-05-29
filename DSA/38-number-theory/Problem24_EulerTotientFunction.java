package numbertheory;

/**
 * Problem 24: Euler Totient Function
 * 
 * Approach: phi(n) = n * product(1 - 1/p) for all prime factors p of n.
 * 
 * Time Complexity: O(sqrt(n))
 * Space Complexity: O(1)
 */
public class Problem24_EulerTotientFunction {
    
    public int eulerTotient(int n) {
        int result = n;
        for (int p = 2; p * p <= n; p++) {
            if (n % p == 0) {
                while (n % p == 0) n /= p;
                result -= result / p;
            }
        }
        if (n > 1) result -= result / n;
        return result;
    }
    
    public static void main(String[] args) {
        Problem24_EulerTotientFunction sol = new Problem24_EulerTotientFunction();
        System.out.println(sol.eulerTotient(12)); // 4
        System.out.println(sol.eulerTotient(36)); // 12
        System.out.println(sol.eulerTotient(7));  // 6
    }
}
