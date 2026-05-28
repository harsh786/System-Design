/**
 * Problem 2: Two Sum II - Input Array Is Sorted
 * 
 * Given a 1-indexed sorted array, find two numbers that add up to target.
 * 
 * Approach: Two pointers from ends. If sum < target, move left. If sum > target, move right.
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like a load balancer pairing light and heavy requests to
 * hit a target throughput - adjusting from both ends of the request queue.
 */
import java.util.Arrays;

public class Problem02_TwoSumII {
    public static int[] twoSum(int[] numbers, int target) {
        int left = 0, right = numbers.length - 1;
        while (left < right) {
            int sum = numbers[left] + numbers[right];
            if (sum == target) return new int[]{left + 1, right + 1};
            else if (sum < target) left++;
            else right--;
        }
        return new int[]{-1, -1};
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(twoSum(new int[]{2,7,11,15}, 9))); // [1,2]
        System.out.println(Arrays.toString(twoSum(new int[]{2,3,4}, 6))); // [1,3]
        System.out.println(Arrays.toString(twoSum(new int[]{-1,0}, -1))); // [1,2]
    }
}
