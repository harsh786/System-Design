import java.util.*;

public class Problem10_LongestContinuousSubarrayWithAbsoluteDiffLimit {
    // LC 1438: Longest subarray where abs diff between any two elements <= limit
    public static int longestSubarray(int[] nums, int limit) {
        TreeMap<Integer, Integer> map = new TreeMap<>();
        int left = 0, ans = 0;
        for (int right = 0; right < nums.length; right++) {
            map.merge(nums[right], 1, Integer::sum);
            while (map.lastKey() - map.firstKey() > limit) {
                map.merge(nums[left], -1, Integer::sum);
                if (map.get(nums[left]) == 0) map.remove(nums[left]);
                left++;
            }
            ans = Math.max(ans, right - left + 1);
        }
        return ans;
    }

    public static void main(String[] args) {
        System.out.println(longestSubarray(new int[]{8,2,4,7}, 4)); // 2
        System.out.println(longestSubarray(new int[]{10,1,2,4,7,2}, 5)); // 4
    }
}
