import java.util.Arrays;

public class Problem32_PartitionToKEqualSumSubsets {
    public boolean canPartitionKSubsets(int[] nums, int k) {
        int sum = Arrays.stream(nums).sum();
        if (sum % k != 0) return false;
        int target = sum / k;
        Arrays.sort(nums);
        return dfs(nums, new boolean[nums.length], k, 0, 0, target);
    }
    private boolean dfs(int[] nums, boolean[] used, int k, int curSum, int start, int target) {
        if (k == 0) return true;
        if (curSum == target) return dfs(nums, used, k-1, 0, 0, target);
        for (int i = start; i < nums.length; i++) {
            if (used[i] || curSum+nums[i]>target) continue;
            if (i > 0 && nums[i]==nums[i-1] && !used[i-1]) continue;
            used[i]=true; if (dfs(nums,used,k,curSum+nums[i],i+1,target)) return true; used[i]=false;
        }
        return false;
    }
    public static void main(String[] args) { System.out.println(new Problem32_PartitionToKEqualSumSubsets().canPartitionKSubsets(new int[]{4,3,2,3,5,2,1},4)); }
}
