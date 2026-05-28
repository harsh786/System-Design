/**
 * Problem 35: Find the Duplicate Number
 * 
 * Array of n+1 integers in range [1,n]. Find the duplicate without modifying array.
 * 
 * Approach: Floyd's cycle detection - treat values as next pointers.
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like detecting a duplicate primary key in a linked
 * data structure by cycle detection rather than using extra storage.
 */
public class Problem35_FindDuplicateNumber {
    public static int findDuplicate(int[] nums) {
        int slow = nums[0], fast = nums[0];
        do { slow = nums[slow]; fast = nums[nums[fast]]; } while (slow != fast);
        slow = nums[0];
        while (slow != fast) { slow = nums[slow]; fast = nums[fast]; }
        return slow;
    }

    public static void main(String[] args) {
        System.out.println(findDuplicate(new int[]{1,3,4,2,2})); // 2
        System.out.println(findDuplicate(new int[]{3,1,3,4,2})); // 3
        System.out.println(findDuplicate(new int[]{1,1})); // 1
    }
}
