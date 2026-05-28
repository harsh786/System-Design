import java.util.*;

/**
 * Problem 19: 4Sum
 * Find all unique quadruplets that sum to target.
 * 
 * Production Analogy: Like multi-dimensional query optimization - reduce N-dimensional
 * problem by fixing dimensions one at a time (layered filtering in search).
 * 
 * O(n^3) time, O(1) extra space - sort + fix two, two-pointer on rest
 */
public class Problem19_FourSum {

    public static List<List<Integer>> fourSum(int[] nums, int target) {
        List<List<Integer>> result = new ArrayList<>();
        Arrays.sort(nums);
        int n = nums.length;
        for (int i = 0; i < n - 3; i++) {
            if (i > 0 && nums[i] == nums[i-1]) continue;
            for (int j = i + 1; j < n - 2; j++) {
                if (j > i + 1 && nums[j] == nums[j-1]) continue;
                int lo = j + 1, hi = n - 1;
                while (lo < hi) {
                    long sum = (long)nums[i] + nums[j] + nums[lo] + nums[hi];
                    if (sum == target) {
                        result.add(Arrays.asList(nums[i], nums[j], nums[lo], nums[hi]));
                        while (lo < hi && nums[lo] == nums[lo+1]) lo++;
                        while (lo < hi && nums[hi] == nums[hi-1]) hi--;
                        lo++; hi--;
                    } else if (sum < target) lo++;
                    else hi--;
                }
            }
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(fourSum(new int[]{1,0,-1,0,-2,2}, 0)); // [[-2,-1,1,2],[-2,0,0,2],[-1,0,0,1]]
        System.out.println(fourSum(new int[]{2,2,2,2,2}, 8));      // [[2,2,2,2]]
    }
}
