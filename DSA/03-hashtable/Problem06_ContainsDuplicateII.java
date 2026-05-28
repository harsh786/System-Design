import java.util.*;

/**
 * Problem 6: Contains Duplicate II
 * Check if there are two distinct indices i,j such that nums[i]==nums[j] and |i-j|<=k.
 *
 * Approach: HashMap storing value -> last seen index. Check distance when duplicate found.
 * Alternative: Sliding window HashSet of size k.
 *
 * Time Complexity: O(n)
 * Space Complexity: O(min(n, k))
 *
 * Production Analogy: Detecting duplicate requests within a time window (idempotency check),
 * like preventing double-submission in payment processing within k seconds.
 */
public class Problem06_ContainsDuplicateII {
    public boolean containsNearbyDuplicate(int[] nums, int k) {
        Map<Integer, Integer> map = new HashMap<>();
        for (int i = 0; i < nums.length; i++) {
            if (map.containsKey(nums[i]) && i - map.get(nums[i]) <= k) {
                return true;
            }
            map.put(nums[i], i);
        }
        return false;
    }

    // Sliding window approach - O(min(n,k)) space
    public boolean containsNearbyDuplicateSet(int[] nums, int k) {
        Set<Integer> window = new HashSet<>();
        for (int i = 0; i < nums.length; i++) {
            if (i > k) window.remove(nums[i - k - 1]);
            if (!window.add(nums[i])) return true;
        }
        return false;
    }

    public static void main(String[] args) {
        Problem06_ContainsDuplicateII sol = new Problem06_ContainsDuplicateII();
        System.out.println(sol.containsNearbyDuplicate(new int[]{1,2,3,1}, 3)); // true
        System.out.println(sol.containsNearbyDuplicate(new int[]{1,0,1,1}, 1)); // true
        System.out.println(sol.containsNearbyDuplicate(new int[]{1,2,3,1,2,3}, 2)); // false
        System.out.println(sol.containsNearbyDuplicateSet(new int[]{1,2,3,1}, 3)); // true
    }
}
