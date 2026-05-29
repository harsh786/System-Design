package numbertheory;

/**
 * Problem 22: Extended GCD (Extended Euclidean Algorithm)
 * 
 * Approach: Find x, y such that ax + by = gcd(a, b).
 * 
 * Time Complexity: O(log(min(a,b)))
 * Space Complexity: O(log(min(a,b))) for recursion
 */
public class Problem22_ExtendedGCD {
    
    // Returns {gcd, x, y} where ax + by = gcd
    public long[] extGcd(long a, long b) {
        if (b == 0) return new long[]{a, 1, 0};
        long[] res = extGcd(b, a % b);
        long g = res[0], x = res[2], y = res[1] - (a / b) * res[2];
        return new long[]{g, x, y};
    }
    
    // Modular inverse of a mod m (when gcd(a,m)=1)
    public long modInverse(long a, long m) {
        long[] res = extGcd(a % m + m, m);
        return (res[1] % m + m) % m;
    }
    
    public static void main(String[] args) {
        Problem22_ExtendedGCD sol = new Problem22_ExtendedGCD();
        long[] res = sol.extGcd(35, 15);
        System.out.printf("gcd=%d, x=%d, y=%d (35*%d + 15*%d = %d)%n", res[0], res[1], res[2], res[1], res[2], 35*res[1]+15*res[2]);
        System.out.println(sol.modInverse(3, 7)); // 5 (3*5 = 15 = 1 mod 7)
    }
}
