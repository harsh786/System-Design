package segmenttree;

import java.util.*;

/**
 * Problem 22: Count of Range Sum (LeetCode 327)
 * 
 * Approach: Compute prefix sums, coordinate compress them, use segment tree to count
 * prefix[j] such that lower <= prefix[i] - prefix[j] <= upper for j < i.
 * 
 * Time Complexity: O(n log n)
 * Space Complexity: O(n)
 */
public class Problem22_CountOfRangeSum {
    
    private int[] tree;
    private int sz;
    
    public int countRangeSum(int[] nums, int lower, int upper) {
        int n = nums.length;
        long[] prefix = new long[n + 1];
        for (int i = 0; i < n; i++) prefix[i + 1] = prefix[i] + nums[i];
        
        // Collect all values needed
        TreeSet<Long> set = new TreeSet<>();
        for (long p : prefix) { set.add(p); set.add(p - lower); set.add(p - upper); }
        Map<Long, Integer> map = new HashMap<>();
        int idx = 0;
        for (long v : set) map.put(v, idx++);
        
        sz = map.size();
        tree = new int[4 * sz];
        int count = 0;
        
        for (int i = 0; i <= n; i++) {
            // Query: count prefix[j] in [prefix[i] - upper, prefix[i] - lower]
            int lo = map.get(prefix[i] - upper);
            int hi = map.get(prefix[i] - lower);
            if (i > 0) count += query(1, 0, sz - 1, lo, hi);
            update(1, 0, sz - 1, map.get(prefix[i]));
        }
        return count;
    }
    
    private void update(int node, int s, int e, int idx) {
        if (s == e) { tree[node]++; return; }
        int mid = (s + e) / 2;
        if (idx <= mid) update(2 * node, s, mid, idx);
        else update(2 * node + 1, mid + 1, e, idx);
        tree[node] = tree[2 * node] + tree[2 * node + 1];
    }
    
    private int query(int node, int s, int e, int l, int r) {
        if (l > r || r < s || e < l) return 0;
        if (l <= s && e <= r) return tree[node];
        int mid = (s + e) / 2;
        return query(2 * node, s, mid, l, r) + query(2 * node + 1, mid + 1, e, l, r);
    }
    
    public static void main(String[] args) {
        Problem22_CountOfRangeSum sol = new Problem22_CountOfRangeSum();
        System.out.println(sol.countRangeSum(new int[]{-2, 5, -1}, -2, 2)); // 3
    }
}
