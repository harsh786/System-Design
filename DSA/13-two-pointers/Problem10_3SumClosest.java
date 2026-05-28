/**
 * Problem 10: 3Sum Closest
 * 
 * Find three integers whose sum is closest to target.
 * 
 * Approach: Sort, fix one, two pointers for pair, track closest sum.
 * Time: O(n^2), Space: O(1)
 * 
 * Production Analogy: Like selecting 3 cache shard sizes that most closely
 * match available memory on a node.
 */
import java.util.Arrays;

public class Problem10_3SumClosest {
    public static int threeSumClosest(int[] nums, int target) {
        Arrays.sort(nums);
        int closest = nums[0] + nums[1] + nums[2];
        for (int i = 0; i < nums.length - 2; i++) {
            int left = i + 1, right = nums.length - 1;
            while (left < right) {
                int sum = nums[i] + nums[left] + nums[right];
                if (Math.abs(sum - target) < Math.abs(closest - target)) closest = sum;
                if (sum < target) left++;
                else if (sum > target) right--;
                else return sum;
            }
        }
        return closest;
    }

    public static void main(String[] args) {
        System.out.println(threeSumClosest(new int[]{-1,2,1,-4}, 1)); // 2
        System.out.println(threeSumClosest(new int[]{0,0,0}, 1)); // 0
    }
}
