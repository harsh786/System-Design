/**
 * Problem 36: Find Pivot Index
 * Find index where sum of left elements == sum of right elements.
 * 
 * Production Analogy: Like finding the load balancing split point in a shard key range -
 * equal weight on both sides.
 * 
 * O(n) time, O(1) space - prefix sum comparison
 */
public class Problem36_FindPivotIndex {

    public static int pivotIndex(int[] nums) {
        int total = 0, leftSum = 0;
        for (int n : nums) total += n;
        for (int i = 0; i < nums.length; i++) {
            if (leftSum == total - leftSum - nums[i]) return i;
            leftSum += nums[i];
        }
        return -1;
    }

    public static void main(String[] args) {
        System.out.println(pivotIndex(new int[]{1,7,3,6,5,6})); // 3
        System.out.println(pivotIndex(new int[]{1,2,3}));        // -1
        System.out.println(pivotIndex(new int[]{2,1,-1}));       // 0
    }
}
