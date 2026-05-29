/**
 * Problem: Least Number of Unique Integers after K Removals (LeetCode 1481)
 * Approach: Count frequencies, sort by frequency, remove least frequent first
 * Complexity: O(n log n) time, O(n) space
 * Production Analogy: Cache eviction - removing least valuable items first (LFU)
 */
import java.util.*;
public class Problem43_LeastNumberUniqueIntegers {
    public int findLeastNumOfUniqueInts(int[] arr, int k) {
        Map<Integer, Integer> freq = new HashMap<>();
        for (int n : arr) freq.merge(n, 1, Integer::sum);
        List<Integer> counts = new ArrayList<>(freq.values());
        Collections.sort(counts);
        int removed = 0;
        for (int i = 0; i < counts.size(); i++) {
            if (k >= counts.get(i)) { k -= counts.get(i); removed++; }
            else break;
        }
        return counts.size() - removed;
    }
    public static void main(String[] args) {
        System.out.println(new Problem43_LeastNumberUniqueIntegers()
            .findLeastNumOfUniqueInts(new int[]{5,5,4}, 1)); // 1
    }
}
