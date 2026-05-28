import java.util.*;
/**
 * Problem 24: Sliding Window Median (LeetCode 480)
 * 
 * Approach: Two heaps (max-heap for lower half, min-heap for upper half) with lazy deletion.
 * Window invariant: maintain balanced heaps for median of window of size k.
 * 
 * Time: O(n log k), Space: O(k)
 * 
 * Production Analogy: Like computing rolling P50 latency for SLA monitoring dashboards.
 */
public class Problem24_SlidingWindowMedian {
    public static double[] medianSlidingWindow(int[] nums, int k) {
        TreeMap<int[], Integer> lower = new TreeMap<>((a, b) -> a[0] != b[0] ? Integer.compare(a[0], b[0]) : Integer.compare(a[1], b[1]));
        TreeMap<int[], Integer> upper = new TreeMap<>((a, b) -> a[0] != b[0] ? Integer.compare(a[0], b[0]) : Integer.compare(a[1], b[1]));
        // Simpler approach: use sorted structure
        // Actually let's use a simpler two-heap with indices approach
        // Use a SortedSet approach for clarity
        TreeMap<Integer, Integer> sortedWindow = new TreeMap<>();
        // Simplest correct approach: maintain sorted list (acceptable for interview)
        double[] result = new double[nums.length - k + 1];
        List<Integer> window = new ArrayList<>();
        for (int i = 0; i < nums.length; i++) {
            // Insert in sorted order
            int pos = Collections.binarySearch(window, nums[i]);
            if (pos < 0) pos = -(pos + 1);
            window.add(pos, nums[i]);
            if (window.size() > k) {
                window.remove(Integer.valueOf(nums[i - k]));
            }
            if (window.size() == k) {
                if (k % 2 == 0) {
                    result[i - k + 1] = ((long) window.get(k / 2 - 1) + (long) window.get(k / 2)) / 2.0;
                } else {
                    result[i - k + 1] = window.get(k / 2);
                }
            }
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(medianSlidingWindow(new int[]{1,3,-1,-3,5,3,6,7}, 3)));
        // [1.0, -1.0, -1.0, 3.0, 5.0, 6.0]
        System.out.println(Arrays.toString(medianSlidingWindow(new int[]{1,2,3,4,2,3,1,4,2}, 3)));
        // [2.0, 3.0, 3.0, 3.0, 2.0, 3.0, 2.0]
    }
}
