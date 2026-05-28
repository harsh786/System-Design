/**
 * Problem 34: Reduce Array Size to The Half (LeetCode 1338)
 *
 * Greedy Choice: Remove elements with highest frequency first.
 *
 * Time: O(n log n), Space: O(n)
 *
 * Production Analogy: Cache eviction - remove most frequent duplicates to halve storage.
 */
import java.util.*;
public class Problem34_ReduceArraySizeToHalf {
    
    public static int minSetSize(int[] arr) {
        Map<Integer, Integer> freq = new HashMap<>();
        for (int a : arr) freq.merge(a, 1, Integer::sum);
        List<Integer> counts = new ArrayList<>(freq.values());
        counts.sort(Collections.reverseOrder());
        int removed = 0, sets = 0, half = arr.length / 2;
        for (int c : counts) {
            removed += c;
            sets++;
            if (removed >= half) return sets;
        }
        return sets;
    }
    
    public static void main(String[] args) {
        System.out.println(minSetSize(new int[]{3,3,3,3,5,5,5,2,2,7})); // 2
        System.out.println(minSetSize(new int[]{7,7,7,7,7,7}));          // 1
    }
}
