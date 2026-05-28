import java.util.*;
/**
 * Problem 22: Contains Duplicate III (LeetCode 220)
 * 
 * Approach: Bucket sort / TreeSet with sliding window of size k.
 * Window invariant: window contains at most k elements (indices within k).
 * Check if any two values differ by at most valueDiff.
 * 
 * Time: O(n log k) with TreeSet, Space: O(k)
 * 
 * Production Analogy: Like detecting near-duplicate transactions within a time
 * window for fraud detection.
 */
public class Problem22_ContainsDuplicateIII {
    public static boolean containsNearbyAlmostDuplicate(int[] nums, int indexDiff, int valueDiff) {
        TreeSet<Long> set = new TreeSet<>();
        for (int i = 0; i < nums.length; i++) {
            long val = (long) nums[i];
            Long ceiling = set.ceiling(val - valueDiff);
            if (ceiling != null && ceiling <= val + valueDiff) return true;
            set.add(val);
            if (i >= indexDiff) set.remove((long) nums[i - indexDiff]);
        }
        return false;
    }

    public static void main(String[] args) {
        System.out.println(containsNearbyAlmostDuplicate(new int[]{1,2,3,1}, 3, 0));      // true
        System.out.println(containsNearbyAlmostDuplicate(new int[]{1,5,9,1,5,9}, 2, 3));  // false
        System.out.println(containsNearbyAlmostDuplicate(new int[]{1,2,1,1}, 1, 0));      // true
    }
}
