import java.math.BigInteger;

/**
 * Problem 23: Karatsuba Multiplication
 * 
 * D&C Approach:
 * - DIVIDE: Split n-digit numbers into two halves: x = a*10^m + b, y = c*10^m + d
 * - CONQUER: Compute 3 multiplications instead of 4:
 *   ac, bd, (a+b)(c+d) - ac - bd = ad+bc
 * - COMBINE: x*y = ac*10^(2m) + (ad+bc)*10^m + bd
 * 
 * Recurrence: T(n) = 3T(n/2) + O(n)
 * Time: O(n^log2(3)) ≈ O(n^1.585) vs naive O(n^2)
 * Space: O(n log n)
 * 
 * Production Analogy:
 * - Big number arithmetic in cryptographic libraries (GMP, OpenSSL)
 * - Polynomial multiplication in signal processing
 * - Foundation for FFT-based multiplication (Schönhage–Strassen)
 */
public class Problem23_KaratsubaMultiplication {

    public static BigInteger karatsuba(BigInteger x, BigInteger y) {
        int n = Math.max(x.bitLength(), y.bitLength());
        if (n <= 32) return x.multiply(y); // Base case: use naive for small numbers
        
        int m = n / 2;
        BigInteger high1 = x.shiftRight(m);
        BigInteger low1 = x.subtract(high1.shiftLeft(m));
        BigInteger high2 = y.shiftRight(m);
        BigInteger low2 = y.subtract(high2.shiftLeft(m));
        
        // Three recursive multiplications (instead of four)
        BigInteger z0 = karatsuba(low1, low2);
        BigInteger z2 = karatsuba(high1, high2);
        BigInteger z1 = karatsuba(high1.add(low1), high2.add(low2)).subtract(z2).subtract(z0);
        
        return z2.shiftLeft(2 * m).add(z1.shiftLeft(m)).add(z0);
    }

    // Simple string-based version for demonstration
    public static long karatsubaSimple(long x, long y) {
        if (x < 10 || y < 10) return x * y;
        
        int n = Math.max(Long.toString(x).length(), Long.toString(y).length());
        int m = n / 2;
        long pow = (long) Math.pow(10, m);
        
        long a = x / pow, b = x % pow;
        long c = y / pow, d = y % pow;
        
        long ac = karatsubaSimple(a, c);
        long bd = karatsubaSimple(b, d);
        long adbc = karatsubaSimple(a + b, c + d) - ac - bd;
        
        return ac * pow * pow + adbc * pow + bd;
    }

    public static void main(String[] args) {
        System.out.println(karatsubaSimple(1234, 5678)); // 7006652
        System.out.println(karatsubaSimple(12, 34));     // 408
        System.out.println(karatsubaSimple(999, 999));   // 998001
        
        BigInteger a = new BigInteger("3141592653589793238462643383279502884197");
        BigInteger b = new BigInteger("2718281828459045235360287471352662497757");
        System.out.println(karatsuba(a, b).equals(a.multiply(b))); // true
    }
}
