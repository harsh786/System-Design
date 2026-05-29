public class Problem38_CountIncreasingQuadruplets {
    public long countQuadruplets(int[] nums) {
        int n = nums.length;
        long result = 0;
        long[] dp = new long[n]; // dp[k] = count of (i,j,k) with nums[i]<nums[k]<nums[j], j<k
        for (int k = 0; k < n; k++) {
            long prevSmall = 0;
            for (int j = 0; j < k; j++) {
                if (nums[j] < nums[k]) {
                    prevSmall++;
                    result += dp[j];
                } else if (nums[j] > nums[k]) {
                    dp[j] += prevSmall;
                }
            }
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(new Problem38_CountIncreasingQuadruplets().countQuadruplets(new int[]{1,3,2,4,5}));
    }
}
