public class Problem47_DivideWithoutDivision {
    // LC 29: Divide two integers without / * or %
    static int divide(int dividend, int divisor) {
        if (dividend == Integer.MIN_VALUE && divisor == -1) return Integer.MAX_VALUE;
        long a = Math.abs((long)dividend), b = Math.abs((long)divisor);
        int result = 0;
        for (int i = 31; i >= 0; i--) {
            if ((a >> i) >= b) { result += (1 << i); a -= (b << i); }
        }
        return (dividend > 0) == (divisor > 0) ? result : -result;
    }
    
    public static void main(String[] args) {
        System.out.println("10/3=" + divide(10, 3));
        System.out.println("7/-2=" + divide(7, -2));
    }
}
