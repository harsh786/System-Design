import java.util.*;

/**
 * Problem 6: Contains Duplicate II
 * Given array nums and int k, return true if there are two distinct indices i and j
 * such that nums[i] == nums[j] and abs(i - j) <= k.
 *
 * Approach: Sliding window HashSet of size k.
 *
 * Time Complexity: O(n)
 * Space Complexity: O(min(n, k))
 *
 * Production Analogy: Like detecting duplicate requests within a time window
 * (idempotency check in API gateways).
 */
public class Problem06_ContainsDuplicateII {
    public boolean containsNearbyDuplicate(int[] nums, int k) {
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
        System.out.println(sol.containsNearbyDuplicate(new int[]{}, 0)); // false
    }
}
