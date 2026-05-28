/**
 * Problem 35: Advantage Shuffle (LeetCode 870)
 *
 * Greedy Choice: For each element in nums2 (largest first), use smallest element in nums1 
 * that beats it. If none can, assign the smallest (sacrifice).
 *
 * Time: O(n log n), Space: O(n)
 *
 * Production Analogy: Optimal matchup strategy - assign cheapest resource that beats competitor.
 */
import java.util.*;
public class Problem35_AdvantageShuffle {
    
    public static int[] advantageCount(int[] nums1, int[] nums2) {
        int n = nums1.length;
        TreeMap<Integer, Integer> map = new TreeMap<>();
        for (int num : nums1) map.merge(num, 1, Integer::sum);
        int[] result = new int[n];
        for (int i = 0; i < n; i++) {
            Integer key = map.higherKey(nums2[i]);
            if (key == null) key = map.firstKey();
            result[i] = key;
            if (map.get(key) == 1) map.remove(key);
            else map.merge(key, -1, Integer::sum);
        }
        return result;
    }
    
    public static void main(String[] args) {
        System.out.println(Arrays.toString(advantageCount(new int[]{2,7,11,15}, new int[]{1,10,4,11})));
        // [2,11,7,15]
        System.out.println(Arrays.toString(advantageCount(new int[]{12,24,8,32}, new int[]{13,25,32,11})));
        // [24,32,8,12]
    }
}
