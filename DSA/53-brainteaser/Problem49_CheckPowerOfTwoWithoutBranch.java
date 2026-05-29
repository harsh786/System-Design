public class Problem49_CheckPowerOfTwoWithoutBranch {
    // Branchless power of 2 check
    static boolean isPow2(int n) { return (n & (n - 1)) == 0 & n > 0; }
    
    // Count trailing zeros (position of single set bit)
    static int log2(int n) { return Integer.numberOfTrailingZeros(n); }
    
    // Next power of 2
    static int nextPow2(int n) { return Integer.highestOneBit(n - 1) << 1; }
    
    public static void main(String[] args) {
        for (int i = 1; i <= 20; i++)
            if (isPow2(i)) System.out.println(i + " is 2^" + log2(i));
        System.out.println("Next pow2 after 13: " + nextPow2(13)); // 16
    }
}
