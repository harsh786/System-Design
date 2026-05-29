import java.util.*;

/**
 * Problem 41: Contains Duplicate III
 * 
 * Check if there exist indices i,j such that abs(nums[i]-nums[j]) <= valueDiff 
 * and abs(i-j) <= indexDiff.
 * 
 * Approach: Bucket sort idea. Bucket size = valueDiff+1. Check same bucket and neighbors.
 * Time Complexity: O(n)
 * Space Complexity: O(indexDiff)
 * 
 * Production Analogy: Rate limiting with tolerance - detecting near-duplicate requests
 * within a time window (e.g., fraud detection for similar transaction amounts).
 */
public class Problem41_ContainsDuplicateIII {
    
    public boolean containsNearbyAlmostDuplicate(int[] nums, int indexDiff, int valueDiff) {
        if (valueDiff < 0) return false;
        Map<Long, Long> buckets = new HashMap<>();
        long w = (long)valueDiff + 1;
        
        for (int i = 0; i < nums.length; i++) {
            long id = getBucketId(nums[i], w);
            
            if (buckets.containsKey(id)) return true;
            if (buckets.containsKey(id - 1) && Math.abs(nums[i] - buckets.get(id - 1)) < w) return true;
            if (buckets.containsKey(id + 1) && Math.abs(nums[i] - buckets.get(id + 1)) < w) return true;
            
            buckets.put(id, (long)nums[i]);
            if (i >= indexDiff) buckets.remove(getBucketId(nums[i - indexDiff], w));
        }
        return false;
    }
    
    private long getBucketId(long num, long w) {
        return num >= 0 ? num / w : (num + 1) / w - 1;
    }
    
    public static void main(String[] args) {
        Problem41_ContainsDuplicateIII sol = new Problem41_ContainsDuplicateIII();
        
        System.out.println("Test 1: " + sol.containsNearbyAlmostDuplicate(new int[]{1,2,3,1}, 3, 0)); // true
        System.out.println("Test 2: " + sol.containsNearbyAlmostDuplicate(new int[]{1,5,9,1,5,9}, 2, 3)); // false
        System.out.println("Test 3: " + sol.containsNearbyAlmostDuplicate(new int[]{-2147483648,2147483647}, 1, 1)); // false
        System.out.println("Test 4: " + sol.containsNearbyAlmostDuplicate(new int[]{1,2}, 0, 1)); // false
    }
}
