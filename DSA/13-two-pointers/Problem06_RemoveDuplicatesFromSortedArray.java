/**
 * Problem 6: Remove Duplicates from Sorted Array
 * 
 * Remove duplicates in-place, return new length.
 * 
 * Approach: Slow/fast pointer. Slow marks position to write, fast scans ahead.
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like deduplicating sorted log entries in a streaming
 * pipeline - one pointer writes unique entries, another scans incoming.
 */
public class Problem06_RemoveDuplicatesFromSortedArray {
    public static int removeDuplicates(int[] nums) {
        if (nums.length == 0) return 0;
        int slow = 0;
        for (int fast = 1; fast < nums.length; fast++) {
            if (nums[fast] != nums[slow]) {
                slow++;
                nums[slow] = nums[fast];
            }
        }
        return slow + 1;
    }

    public static void main(String[] args) {
        System.out.println(removeDuplicates(new int[]{1,1,2})); // 2
        System.out.println(removeDuplicates(new int[]{0,0,1,1,1,2,2,3,3,4})); // 5
        System.out.println(removeDuplicates(new int[]{1})); // 1
    }
}
