package segmenttree;

/**
 * Problem 38: Segment Tree for Dynamic LIS
 * 
 * Approach: Segment tree on value range. For each element, query max LIS ending at values < current,
 * then update current position with that + 1.
 * 
 * Time Complexity: O(n log m) where m is value range
 * Space Complexity: O(m)
 */
public class Problem38_SegmentTreeForDynamicLIS {
    
    private int[] tree;
    private int size;
    
    public int lengthOfLIS(int[] nums) {
        int max = 0;
        for (int v : nums) max = Math.max(max, v);
        size = max + 2;
        tree = new int[4 * size];
        int ans = 0;
        for (int num : nums) {
            int best = query(1, 0, size - 1, 0, num - 1);
            int cur = best + 1;
            ans = Math.max(ans, cur);
            update(1, 0, size - 1, num, cur);
        }
        return ans;
    }
    
    private void update(int o, int s, int e, int idx, int val) {
        if (s == e) { tree[o] = Math.max(tree[o], val); return; }
        int mid = (s + e) / 2;
        if (idx <= mid) update(2 * o, s, mid, idx, val);
        else update(2 * o + 1, mid + 1, e, idx, val);
        tree[o] = Math.max(tree[2 * o], tree[2 * o + 1]);
    }
    
    private int query(int o, int s, int e, int l, int r) {
        if (l > r || r < s || e < l) return 0;
        if (l <= s && e <= r) return tree[o];
        int mid = (s + e) / 2;
        return Math.max(query(2 * o, s, mid, l, r), query(2 * o + 1, mid + 1, e, l, r));
    }
    
    public static void main(String[] args) {
        Problem38_SegmentTreeForDynamicLIS sol = new Problem38_SegmentTreeForDynamicLIS();
        System.out.println(sol.lengthOfLIS(new int[]{10, 9, 2, 5, 3, 7, 101, 18})); // 4
        sol = new Problem38_SegmentTreeForDynamicLIS();
        System.out.println(sol.lengthOfLIS(new int[]{0, 1, 0, 3, 2, 3})); // 4
    }
}
