package segmenttree;

import java.util.*;

/**
 * Problem 49: Segment Tree for Count in Range
 * 
 * Approach: Merge sort tree to count elements in [lo, hi] within index range [l, r].
 * 
 * Time Complexity: O(n log n) build, O(log^2 n) per query
 * Space Complexity: O(n log n)
 */
public class Problem49_SegmentTreeForCountInRange {
    
    private List<Integer>[] tree;
    private int n;
    
    @SuppressWarnings("unchecked")
    public Problem49_SegmentTreeForCountInRange(int[] arr) {
        n = arr.length; tree = new List[4*n];
        for (int i = 0; i < 4*n; i++) tree[i] = new ArrayList<>();
        build(1, 0, n-1, arr);
    }
    
    private void build(int o, int s, int e, int[] arr) {
        if (s == e) { tree[o].add(arr[s]); return; }
        int mid = (s+e)/2;
        build(2*o, s, mid, arr); build(2*o+1, mid+1, e, arr);
        int i = 0, j = 0;
        while (i < tree[2*o].size() && j < tree[2*o+1].size()) {
            if (tree[2*o].get(i) <= tree[2*o+1].get(j)) tree[o].add(tree[2*o].get(i++));
            else tree[o].add(tree[2*o+1].get(j++));
        }
        while (i < tree[2*o].size()) tree[o].add(tree[2*o].get(i++));
        while (j < tree[2*o+1].size()) tree[o].add(tree[2*o+1].get(j++));
    }
    
    public int countInRange(int l, int r, int lo, int hi) { return query(1, 0, n-1, l, r, lo, hi); }
    
    private int query(int o, int s, int e, int l, int r, int lo, int hi) {
        if (r < s || e < l) return 0;
        if (l <= s && e <= r) return upperBound(tree[o], hi) - lowerBound(tree[o], lo);
        int mid = (s+e)/2;
        return query(2*o, s, mid, l, r, lo, hi) + query(2*o+1, mid+1, e, l, r, lo, hi);
    }
    
    private int lowerBound(List<Integer> list, int val) {
        int lo = 0, hi = list.size();
        while (lo < hi) { int mid = (lo+hi)/2; if (list.get(mid) < val) lo = mid+1; else hi = mid; }
        return lo;
    }
    
    private int upperBound(List<Integer> list, int val) {
        int lo = 0, hi = list.size();
        while (lo < hi) { int mid = (lo+hi)/2; if (list.get(mid) <= val) lo = mid+1; else hi = mid; }
        return lo;
    }
    
    public static void main(String[] args) {
        Problem49_SegmentTreeForCountInRange st = new Problem49_SegmentTreeForCountInRange(new int[]{3,1,4,1,5,9,2,6});
        System.out.println(st.countInRange(0, 7, 2, 5)); // 5 (3,4,5,2 + one of the 1s? No: 3,4,5,2 = 4... let me check: values in [2,5]: 3,4,5,2 = 4)
        System.out.println(st.countInRange(0, 3, 1, 3)); // 3 (3,1,1)
    }
}
