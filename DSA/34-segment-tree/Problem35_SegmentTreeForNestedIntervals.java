package segmenttree;

import java.util.*;

/**
 * Problem 35: Segment Tree for Nested Intervals
 * 
 * Approach: Sort intervals by left endpoint ascending, right descending.
 * Use segment tree on compressed right endpoints to count how many previous intervals
 * have right >= current right (those nest current interval).
 * 
 * Time Complexity: O(n log n)
 * Space Complexity: O(n)
 */
public class Problem35_SegmentTreeForNestedIntervals {
    
    private int[] tree;
    
    public int[] countNesting(int[][] intervals) {
        int n = intervals.length;
        int[][] arr = new int[n][3];
        for (int i = 0; i < n; i++) { arr[i][0] = intervals[i][0]; arr[i][1] = intervals[i][1]; arr[i][2] = i; }
        Arrays.sort(arr, (a, b) -> a[0] != b[0] ? a[0] - b[0] : b[1] - a[1]);
        
        // Compress right values
        int[] rights = new int[n];
        for (int i = 0; i < n; i++) rights[i] = arr[i][1];
        int[] sorted = rights.clone();
        Arrays.sort(sorted);
        sorted = Arrays.stream(sorted).distinct().toArray();
        int sz = sorted.length;
        tree = new int[4 * sz];
        
        int[] result = new int[n];
        for (int i = 0; i < n; i++) {
            int rIdx = Arrays.binarySearch(sorted, arr[i][1]);
            // Count intervals already inserted with right >= arr[i][1]
            result[arr[i][2]] = query(1, 0, sz - 1, rIdx, sz - 1);
            update(1, 0, sz - 1, rIdx);
        }
        return result;
    }
    
    private void update(int o, int s, int e, int idx) {
        if (s == e) { tree[o]++; return; }
        int mid = (s + e) / 2;
        if (idx <= mid) update(2 * o, s, mid, idx);
        else update(2 * o + 1, mid + 1, e, idx);
        tree[o] = tree[2 * o] + tree[2 * o + 1];
    }
    
    private int query(int o, int s, int e, int l, int r) {
        if (r < s || e < l) return 0;
        if (l <= s && e <= r) return tree[o];
        int mid = (s + e) / 2;
        return query(2 * o, s, mid, l, r) + query(2 * o + 1, mid + 1, e, l, r);
    }
    
    public static void main(String[] args) {
        Problem35_SegmentTreeForNestedIntervals sol = new Problem35_SegmentTreeForNestedIntervals();
        int[] res = sol.countNesting(new int[][]{{1,8},{2,6},{3,4},{2,9}});
        System.out.println(Arrays.toString(res)); // intervals nested by how many others
    }
}
