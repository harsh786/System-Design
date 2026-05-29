import java.util.*;

public class Problem43_LasVegasVsMonteCarloComparison {
    static Random rand = new Random();

    // Las Vegas: always correct, random runtime (e.g., randomized quicksort)
    static int lasVegasFind(int[] arr, int target) {
        List<Integer> indices = new ArrayList<>();
        for (int i = 0; i < arr.length; i++) indices.add(i);
        Collections.shuffle(indices, rand);
        for (int i : indices) if (arr[i] == target) return i;
        return -1;
    }

    // Monte Carlo: might be wrong, bounded runtime (e.g., primality test)
    static boolean monteCarloIsPrime(long n, int k) {
        if (n < 2) return false;
        if (n < 4) return true;
        for (int i = 0; i < k; i++) {
            long a = 2 + (long)(rand.nextDouble() * (n - 3));
            if (modPow(a, n-1, n) != 1) return false;
        }
        return true; // probably prime
    }

    static long modPow(long base, long exp, long mod) {
        long result = 1; base %= mod;
        while (exp > 0) { if ((exp&1)==1) result=result*base%mod; exp>>=1; base=base*base%mod; }
        return result;
    }

    public static void main(String[] args) {
        int[] arr = {5,3,8,1,9};
        System.out.println("Las Vegas find 8: index=" + lasVegasFind(arr, 8));
        System.out.println("Monte Carlo isPrime(97): " + monteCarloIsPrime(97, 10));
        System.out.println("Monte Carlo isPrime(100): " + monteCarloIsPrime(100, 10));
    }
}
