import java.util.*;

public class Problem36_LongestSubarrayWithLimitUsingTreeMap {
    // Same as Problem10 but explicit TreeMap approach
    public static int longestSubarray(int[] nums, int limit) {
        TreeMap<Integer, Integer> map = new TreeMap<>();
        int l = 0, ans = 0;
        for (int r = 0; r < nums.length; r++) {
            map.merge(nums[r], 1, Integer::sum);
            while (map.lastKey() - map.firstKey() > limit) {
                map.merge(nums[l], -1, Integer::sum);
                if (map.get(nums[l]) == 0) map.remove(nums[l]);
                l++;
            }
            ans = Math.max(ans, r - l + 1);
        }
        return ans;
    }

    public static void main(String[] args) {
        System.out.println(longestSubarray(new int[]{8,2,4,7}, 4)); // 2
        System.out.println(longestSubarray(new int[]{4,2,2,2,4,4,2,2}, 0)); // 3
    }
}
