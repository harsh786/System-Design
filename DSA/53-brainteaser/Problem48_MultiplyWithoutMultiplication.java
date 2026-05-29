public class Problem48_MultiplyWithoutMultiplication {
    // Russian peasant multiplication using shifts and adds
    static long multiply(long a, long b) {
        boolean negative = (a < 0) ^ (b < 0);
        a = Math.abs(a); b = Math.abs(b);
        long result = 0;
        while (b > 0) {
            if ((b & 1) == 1) result += a;
            a <<= 1;
            b >>= 1;
        }
        return negative ? -result : result;
    }
    
    public static void main(String[] args) {
        System.out.println("7*6=" + multiply(7, 6));
        System.out.println("13*-3=" + multiply(13, -3));
    }
}
