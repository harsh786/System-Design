public class Problem33_SingleNumberXOR {
    // Every element appears twice except one
    static int singleNumber(int[] nums) { int x = 0; for (int n : nums) x ^= n; return x; }
    
    // Every element appears three times except one
    static int singleNumberII(int[] nums) {
        int ones = 0, twos = 0;
        for (int n : nums) { ones = (ones ^ n) & ~twos; twos = (twos ^ n) & ~ones; }
        return ones;
    }
    
    public static void main(String[] args) {
        System.out.println(singleNumber(new int[]{4,1,2,1,2})); // 4
        System.out.println(singleNumberII(new int[]{2,2,3,2})); // 3
    }
}
