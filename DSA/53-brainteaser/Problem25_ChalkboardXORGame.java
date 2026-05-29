public class Problem25_ChalkboardXORGame {
    // LC 810: Alice wins if XOR is 0 or array length is even
    static boolean xorGame(int[] nums) {
        int xor = 0;
        for (int n : nums) xor ^= n;
        return xor == 0 || nums.length % 2 == 0;
    }
    
    public static void main(String[] args) {
        System.out.println(xorGame(new int[]{1, 1, 2})); // false
        System.out.println(xorGame(new int[]{1, 2, 3})); // true (even not apply, but xor=0)
    }
}
