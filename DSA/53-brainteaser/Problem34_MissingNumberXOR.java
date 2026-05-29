public class Problem34_MissingNumberXOR {
    static int missingNumber(int[] nums) {
        int xor = nums.length;
        for (int i = 0; i < nums.length; i++) xor ^= i ^ nums[i];
        return xor;
    }
    
    public static void main(String[] args) {
        System.out.println(missingNumber(new int[]{3,0,1})); // 2
        System.out.println(missingNumber(new int[]{0,1})); // 2
    }
}
