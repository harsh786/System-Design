/**
 * Problem 16: Majority Element (D&C) - LeetCode 169
 * 
 * D&C Approach:
 * - DIVIDE: Split array into two halves
 * - CONQUER: Find majority element in each half
 * - COMBINE: If both halves agree, that's the answer.
 *   If they disagree, count occurrences of each candidate in the full range.
 * 
 * Recurrence: T(n) = 2T(n/2) + O(n)
 * Time: O(n log n), Space: O(log n)
 * 
 * Production Analogy:
 * - Distributed voting/consensus (each partition votes, reconcile at merge)
 * - Finding dominant category across distributed data shards
 */
public class Problem16_MajorityElement {

    public static int majorityElement(int[] nums) {
        return majority(nums, 0, nums.length - 1);
    }

    private static int majority(int[] nums, int lo, int hi) {
        if (lo == hi) return nums[lo];
        
        int mid = lo + (hi - lo) / 2;
        int left = majority(nums, lo, mid);
        int right = majority(nums, mid + 1, hi);
        
        if (left == right) return left;
        
        int leftCount = count(nums, left, lo, hi);
        int rightCount = count(nums, right, lo, hi);
        return leftCount > rightCount ? left : right;
    }

    private static int count(int[] nums, int target, int lo, int hi) {
        int c = 0;
        for (int i = lo; i <= hi; i++) if (nums[i] == target) c++;
        return c;
    }

    public static void main(String[] args) {
        System.out.println(majorityElement(new int[]{3,2,3}));           // 3
        System.out.println(majorityElement(new int[]{2,2,1,1,1,2,2}));   // 2
        System.out.println(majorityElement(new int[]{1}));               // 1
        System.out.println(majorityElement(new int[]{6,6,6,7,7}));       // 6
    }
}
