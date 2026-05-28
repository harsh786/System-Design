/**
 * Problem 48: 3Sum Smaller
 * 
 * Count triplets with sum less than target.
 * 
 * Approach: Sort, fix one, two pointers. If sum < target, all pairs between left and right work.
 * Time: O(n^2), Space: O(1)
 * 
 * Production Analogy: Like counting all possible 3-service deployments whose
 * combined resource usage stays below a budget limit.
 */
import java.util.Arrays;

public class Problem48_3SumSmaller {
    public static int threeSumSmaller(int[] nums, int target) {
        Arrays.sort(nums);
        int count = 0;
        for (int i = 0; i < nums.length - 2; i++) {
            int left = i + 1, right = nums.length - 1;
            while (left < right) {
                if (nums[i] + nums[left] + nums[right] < target) {
                    count += right - left; // all pairs (left, left+1...right) work
                    left++;
                } else {
                    right--;
                }
            }
        }
        return count;
    }

    public static void main(String[] args) {
        System.out.println(threeSumSmaller(new int[]{-2,0,1,3}, 2)); // 2
        System.out.println(threeSumSmaller(new int[]{}, 0)); // 0
        System.out.println(threeSumSmaller(new int[]{0}, 0)); // 0
    }
}
