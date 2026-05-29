import java.util.*;

/**
 * Problem 40: Contains Duplicate
 * 
 * Return true if any value appears at least twice.
 * 
 * Approach: HashSet for O(n) time, or sort for O(n log n) time O(1) space.
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Idempotency check in message queues - detecting duplicate message IDs
 * to prevent double-processing.
 */
public class Problem40_ContainsDuplicate {
    
    public boolean containsDuplicate(int[] nums) {
        Set<Integer> seen = new HashSet<>();
        for (int n : nums) {
            if (!seen.add(n)) return true;
        }
        return false;
    }
    
    // Sort-based approach - O(1) extra space
    public boolean containsDuplicateSort(int[] nums) {
        Arrays.sort(nums);
        for (int i = 1; i < nums.length; i++) {
            if (nums[i] == nums[i-1]) return true;
        }
        return false;
    }
    
    public static void main(String[] args) {
        Problem40_ContainsDuplicate sol = new Problem40_ContainsDuplicate();
        
        System.out.println("Test 1: " + sol.containsDuplicate(new int[]{1,2,3,1})); // true
        System.out.println("Test 2: " + sol.containsDuplicate(new int[]{1,2,3,4})); // false
        System.out.println("Test 3: " + sol.containsDuplicate(new int[]{1,1,1,3,3,4,3,2,4,2})); // true
        System.out.println("Test 4: " + sol.containsDuplicate(new int[]{})); // false
    }
}
