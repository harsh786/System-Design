package segmenttree;

import java.util.*;

/**
 * Problem 45: Merge Sort Tree (Concept)
 * 
 * Approach: Each node stores sorted list of elements in its range.
 * Supports queries like "count elements <= k in range [l, r]".
 * 
 * Time Complexity: O(n log n) build, O(log^2 n) per query
 * Space Complexity: O(n log n)
 */
public class Problem45_MergeSortTree {
    
    private List<Integer>[] tree;
    private int n;
    
    @SuppressWarnings("unchecked")
    public Problem45_MergeSortTree(int[] arr) {
        n = arr.length;
        tree = new List[4 * n];
        for (int i = 0; i < 4 * n; i++) tree[i] = new ArrayList<>();
        build(1, 0, n - 1, arr);
    }
    
    private void build(int o, int s, int e, int[] arr) {
        if (s == e) { tree[o].add(arr[s]); return; }
        int mid = (s + e) / 2;
        build(2 * o, s, mid, arr); build(2 * o + 1, mid + 1, e, arr);
        // Merge
        int i = 0, j = 0;
        List<Integer> left = tree[2 * o], right = tree[2 * o + 1];
        while (i < left.size() && j < right.size()) {
            if (left.get(i) <= right.get(j)) tree[o].add(left.get(i++));
            else tree[o].add(right.get(j++));
        }
        while (i < left.size()) tree[o].add(left.get(i++));
        while (j < right.size()) tree[o].add(right.get(j++));
    }
    
    // Count elements <= k in range [l, r]
    public int countLessOrEqual(int l, int r, int k) { return query(1, 0, n - 1, l, r, k); }
    
    private int query(int o, int s, int e, int l, int r, int k) {
        if (r < s || e < l) return 0;
        if (l <= s && e <= r) return upperBound(tree[o], k);
        int mid = (s + e) / 2;
        return query(2 * o, s, mid, l, r, k) + query(2 * o + 1, mid + 1, e, l, r, k);
    }
    
    private int upperBound(List<Integer> list, int k) {
        int lo = 0, hi = list.size();
        while (lo < hi) { int mid = (lo + hi) / 2; if (list.get(mid) <= k) lo = mid + 1; else hi = mid; }
        return lo;
    }
    
    public static void main(String[] args) {
        Problem45_MergeSortTree mst = new Problem45_MergeSortTree(new int[]{3, 1, 4, 1, 5, 9, 2, 6});
        System.out.println(mst.countLessOrEqual(0, 7, 4)); // 5 (3,1,4,1,2)
        System.out.println(mst.countLessOrEqual(2, 5, 5)); // 3 (4,1,5)
    }
}
