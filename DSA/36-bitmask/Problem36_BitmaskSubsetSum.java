public class Problem36_BitmaskSubsetSum {
    public boolean subsetSum(int[] nums, int target) {
        int n = nums.length;
        for (int mask = 0; mask < (1 << n); mask++) {
            int sum = 0;
            for (int i = 0; i < n; i++) if ((mask & (1 << i)) != 0) sum += nums[i];
            if (sum == target) return true;
        }
        return false;
    }

    public static void main(String[] args) {
        System.out.println(new Problem36_BitmaskSubsetSum().subsetSum(new int[]{3,34,4,12,5,2}, 9)); // true
    }
}
