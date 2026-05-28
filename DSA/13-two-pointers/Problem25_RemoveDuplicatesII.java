/**
 * Problem 25: Remove Duplicates from Sorted Array II
 * 
 * Allow at most 2 duplicates.
 * 
 * Approach: Slow pointer writes; only write if nums[fast] != nums[slow-2].
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like rate limiting that allows burst of 2 identical
 * requests but drops subsequent duplicates.
 */
public class Problem25_RemoveDuplicatesII {
    public static int removeDuplicates(int[] nums) {
        if (nums.length <= 2) return nums.length;
        int slow = 2;
        for (int fast = 2; fast < nums.length; fast++) {
            if (nums[fast] != nums[slow - 2]) nums[slow++] = nums[fast];
        }
        return slow;
    }

    public static void main(String[] args) {
        System.out.println(removeDuplicates(new int[]{1,1,1,2,2,3})); // 5
        System.out.println(removeDuplicates(new int[]{0,0,1,1,1,1,2,3,3})); // 7
    }
}
