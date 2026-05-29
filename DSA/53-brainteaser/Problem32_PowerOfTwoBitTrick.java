public class Problem32_PowerOfTwoBitTrick {
    static boolean isPowerOfTwo(int n) { return n > 0 && (n & (n - 1)) == 0; }
    static boolean isPowerOfFour(int n) { return n > 0 && (n & (n-1)) == 0 && (n & 0x55555555) != 0; }
    
    public static void main(String[] args) {
        for (int i = 1; i <= 32; i++)
            if (isPowerOfTwo(i)) System.out.println(i + " isPow2, isPow4=" + isPowerOfFour(i));
    }
}
