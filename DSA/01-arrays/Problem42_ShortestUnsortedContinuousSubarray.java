/**
 * Problem 42: Shortest Unsorted Continuous Subarray
 * Find shortest subarray that, if sorted, makes entire array sorted.
 * 
 * Production Analogy: Like finding the minimum range of data partitions to re-sort
 * after a partial corruption in a distributed sorted index.
 * 
 * O(n) time, O(1) space - find boundaries from both ends
 */
public class Problem42_ShortestUnsortedContinuousSubarray {

    public static int findUnsortedSubarray(int[] nums) {
        int n = nums.length, left = -1, right = -1;
        int max = Integer.MIN_VALUE, min = Integer.MAX_VALUE;
        for (int i = 0; i < n; i++) {
            if (nums[i] < max) right = i;
            else max = nums[i];
        }
        for (int i = n - 1; i >= 0; i--) {
            if (nums[i] > min) left = i;
            else min = nums[i];
        }
        return left == -1 ? 0 : right - left + 1;
    }

    public static void main(String[] args) {
        System.out.println(findUnsortedSubarray(new int[]{2,6,4,8,10,9,15})); // 5
        System.out.println(findUnsortedSubarray(new int[]{1,2,3,4}));          // 0
        System.out.println(findUnsortedSubarray(new int[]{1}));                 // 0
    }
}
