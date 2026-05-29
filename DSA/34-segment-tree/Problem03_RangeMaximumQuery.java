/**
 * Problem 3: Range Maximum Query
 * Approach: Segment tree storing max values.
 * Time: O(log n) per query/update
 * Space: O(n)
 * Production Analogy: Finding peak traffic in any given time range for capacity planning.
 */
public class Problem03_RangeMaximumQuery {
    int[] tree;
    int n;

    public void build(int[] nums) {
        n = nums.length;
        tree = new int[4 * n];
        build(nums, 1, 0, n - 1);
    }

    private void build(int[] nums, int node, int s, int e) {
        if (s == e) { tree[node] = nums[s]; return; }
        int m = (s + e) / 2;
        build(nums, node * 2, s, m);
        build(nums, node * 2 + 1, m + 1, e);
        tree[node] = Math.max(tree[node * 2], tree[node * 2 + 1]);
    }

    public void update(int idx, int val) { update(1, 0, n - 1, idx, val); }

    private void update(int node, int s, int e, int idx, int val) {
        if (s == e) { tree[node] = val; return; }
        int m = (s + e) / 2;
        if (idx <= m) update(node * 2, s, m, idx, val);
        else update(node * 2 + 1, m + 1, e, idx, val);
        tree[node] = Math.max(tree[node * 2], tree[node * 2 + 1]);
    }

    public int query(int l, int r) { return query(1, 0, n - 1, l, r); }

    private int query(int node, int s, int e, int l, int r) {
        if (r < s || e < l) return Integer.MIN_VALUE;
        if (l <= s && e <= r) return tree[node];
        int m = (s + e) / 2;
        return Math.max(query(node * 2, s, m, l, r), query(node * 2 + 1, m + 1, e, l, r));
    }

    public static void main(String[] args) {
        Problem03_RangeMaximumQuery sol = new Problem03_RangeMaximumQuery();
        sol.build(new int[]{2, 5, 1, 4, 9, 3});
        System.out.println("Max [1,4]: " + sol.query(1, 4)); // 9
    }
}
