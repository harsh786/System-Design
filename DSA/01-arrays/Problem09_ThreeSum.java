import java.util.*;

/**
 * Problem 9: 3Sum
 * Find all unique triplets that sum to zero.
 * 
 * Production Analogy: Like finding balanced transaction groups in a ledger -
 * credits and debits that net to zero for reconciliation.
 * 
 * O(n^2) time, O(1) extra space (sorting in place) - sort + two pointers
 */
public class Problem09_ThreeSum {

    public static List<List<Integer>> threeSum(int[] nums) {
        List<List<Integer>> result = new ArrayList<>();
        Arrays.sort(nums);
        for (int i = 0; i < nums.length - 2; i++) {
            if (i > 0 && nums[i] == nums[i-1]) continue;
            int lo = i + 1, hi = nums.length - 1;
            while (lo < hi) {
                int sum = nums[i] + nums[lo] + nums[hi];
                if (sum == 0) {
                    result.add(Arrays.asList(nums[i], nums[lo], nums[hi]));
                    while (lo < hi && nums[lo] == nums[lo+1]) lo++;
                    while (lo < hi && nums[hi] == nums[hi-1]) hi--;
                    lo++; hi--;
                } else if (sum < 0) lo++;
                else hi--;
            }
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(threeSum(new int[]{-1,0,1,2,-1,-4})); // [[-1,-1,2],[-1,0,1]]
        System.out.println(threeSum(new int[]{0,1,1}));           // []
        System.out.println(threeSum(new int[]{0,0,0}));           // [[0,0,0]]
    }
}
