package segmenttree;

import java.util.*;

/**
 * Problem 37: Segment Tree for Inversion Count
 * 
 * Approach: Process array from left to right. For each element, count how many larger elements
 * are already inserted (query range [val+1, max]). Then insert current value.
 * 
 * Time Complexity: O(n log n)
 * Space Complexity: O(n)
 */
public class Problem37_SegmentTreeForInversionCount {
    
    private int[] tree;
    private int size;
    
    public long countInversions(int[] arr) {
        // Coordinate compress
        int[] sorted = arr.clone();
        Arrays.sort(sorted);
        Map<Integer, Integer> map = new HashMap<>();
        int idx = 0;
        for (int v : sorted) if (!map.containsKey(v)) map.put(v, idx++);
        size = idx;
        tree = new int[4 * size];
        
        long inv = 0;
        for (int val : arr) {
            int c = map.get(val);
            inv += query(1, 0, size - 1, c + 1, size - 1);
            update(1, 0, size - 1, c);
        }
        return inv;
    }
    
    private void update(int o, int s, int e, int idx) {
        if (s == e) { tree[o]++; return; }
        int mid = (s + e) / 2;
        if (idx <= mid) update(2 * o, s, mid, idx);
        else update(2 * o + 1, mid + 1, e, idx);
        tree[o] = tree[2 * o] + tree[2 * o + 1];
    }
    
    private int query(int o, int s, int e, int l, int r) {
        if (l > r || r < s || e < l) return 0;
        if (l <= s && e <= r) return tree[o];
        int mid = (s + e) / 2;
        return query(2 * o, s, mid, l, r) + query(2 * o + 1, mid + 1, e, l, r);
    }
    
    public static void main(String[] args) {
        Problem37_SegmentTreeForInversionCount sol = new Problem37_SegmentTreeForInversionCount();
        System.out.println(sol.countInversions(new int[]{5, 3, 2, 4, 1})); // 8
        System.out.println(sol.countInversions(new int[]{1, 2, 3, 4, 5})); // 0
    }
}
