/**
 * Problem 29: Find the Duplicate Number
 * Array of n+1 integers in [1,n], find the duplicate without modifying array.
 * 
 * Production Analogy: Like detecting a cycle in a linked service dependency graph -
 * Floyd's cycle detection finds where the loop starts.
 * 
 * O(n) time, O(1) space - Floyd's Tortoise and Hare (cycle detection)
 */
public class Problem29_FindTheDuplicateNumber {

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
        System.out.println(findDuplicate(new int[]{2,2,2,2,2})); // 2
    }
}
