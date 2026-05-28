/**
 * Problem 26: Remove Element
 * 
 * Remove all occurrences of val in-place, return new length.
 * 
 * Approach: Slow/fast pointer, copy non-val elements forward.
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like filtering out poisoned messages from a queue
 * while preserving order of valid messages.
 */
public class Problem26_RemoveElement {
    public static int removeElement(int[] nums, int val) {
        int slow = 0;
        for (int fast = 0; fast < nums.length; fast++) {
            if (nums[fast] != val) nums[slow++] = nums[fast];
        }
        return slow;
    }

    public static void main(String[] args) {
        System.out.println(removeElement(new int[]{3,2,2,3}, 3)); // 2
        System.out.println(removeElement(new int[]{0,1,2,2,3,0,4,2}, 2)); // 5
    }
}
