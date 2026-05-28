/**
 * Problem 13: 4Sum
 * 
 * Find all unique quadruplets that sum to target.
 * 
 * Approach: Sort, fix two elements, two-pointer for remaining pair.
 * Time: O(n^3), Space: O(1) excluding output
 * 
 * Production Analogy: Like finding 4 microservice replicas whose combined
 * resource allocation exactly matches a provisioned VM size.
 */
import java.util.*;

public class Problem13_4Sum {
    public static List<List<Integer>> fourSum(int[] nums, int target) {
        List<List<Integer>> result = new ArrayList<>();
        Arrays.sort(nums);
        int n = nums.length;
        for (int i = 0; i < n - 3; i++) {
            if (i > 0 && nums[i] == nums[i-1]) continue;
            for (int j = i + 1; j < n - 2; j++) {
                if (j > i + 1 && nums[j] == nums[j-1]) continue;
                int left = j + 1, right = n - 1;
                while (left < right) {
                    long sum = (long)nums[i] + nums[j] + nums[left] + nums[right];
                    if (sum == target) {
                        result.add(Arrays.asList(nums[i], nums[j], nums[left], nums[right]));
                        while (left < right && nums[left] == nums[left+1]) left++;
                        while (left < right && nums[right] == nums[right-1]) right--;
                        left++; right--;
                    } else if (sum < target) left++;
                    else right--;
                }
            }
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(fourSum(new int[]{1,0,-1,0,-2,2}, 0)); // [[-2,-1,1,2],[-2,0,0,2],[-1,0,0,1]]
        System.out.println(fourSum(new int[]{2,2,2,2,2}, 8)); // [[2,2,2,2]]
    }
}
