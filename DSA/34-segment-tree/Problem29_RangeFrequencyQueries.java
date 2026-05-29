package segmenttree;

import java.util.*;

/**
 * Problem 29: Range Frequency Queries (LeetCode 2080)
 * 
 * Approach: Store indices per value, binary search to count occurrences in [left, right].
 * Alternatively, use merge sort tree / segment tree with vectors.
 * Here: simple binary search approach (optimal).
 * 
 * Time Complexity: O(n) build, O(log n) per query
 * Space Complexity: O(n)
 */
public class Problem29_RangeFrequencyQueries {
    
    private Map<Integer, List<Integer>> map;
    
    public Problem29_RangeFrequencyQueries(int[] arr) {
        map = new HashMap<>();
        for (int i = 0; i < arr.length; i++)
            map.computeIfAbsent(arr[i], k -> new ArrayList<>()).add(i);
    }
    
    public int query(int left, int right, int value) {
        List<Integer> indices = map.get(value);
        if (indices == null) return 0;
        int lo = lowerBound(indices, left);
        int hi = upperBound(indices, right);
        return hi - lo;
    }
    
    private int lowerBound(List<Integer> list, int target) {
        int lo = 0, hi = list.size();
        while (lo < hi) { int mid = (lo + hi) / 2; if (list.get(mid) < target) lo = mid + 1; else hi = mid; }
        return lo;
    }
    
    private int upperBound(List<Integer> list, int target) {
        int lo = 0, hi = list.size();
        while (lo < hi) { int mid = (lo + hi) / 2; if (list.get(mid) <= target) lo = mid + 1; else hi = mid; }
        return lo;
    }
    
    public static void main(String[] args) {
        Problem29_RangeFrequencyQueries sol = new Problem29_RangeFrequencyQueries(new int[]{12,33,4,56,22,2,34,33,22,12,34,56});
        System.out.println(sol.query(1, 2, 4));   // 1
        System.out.println(sol.query(0, 11, 33)); // 2
    }
}
