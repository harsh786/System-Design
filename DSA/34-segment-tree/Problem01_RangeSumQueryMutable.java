/**
 * Problem 1: Range Sum Query - Mutable (LeetCode 307)
 * 
 * Approach: Segment Tree with point update and range sum query.
 * Build tree in O(n), update in O(log n), query in O(log n).
 * 
 * Time Complexity: O(n) build, O(log n) update/query
 * Space Complexity: O(n)
 * 
 * Production Analogy: Real-time dashboard aggregating metrics across time windows
 * where individual data points update frequently.
 */
public class Problem01_RangeSumQueryMutable {
    int[] tree;
    int n;

    public void build(int[] nums) {
        n = nums.length;
        tree = new int[4 * n];
        build(nums, 1, 0, n - 1);
    }

    private void build(int[] nums, int node, int start, int end) {
        if (start == end) { tree[node] = nums[start]; return; }
        int mid = (start + end) / 2;
        build(nums, node * 2, start, mid);
        build(nums, node * 2 + 1, mid + 1, end);
        tree[node] = tree[node * 2] + tree[node * 2 + 1];
    }

    public void update(int idx, int val) { update(1, 0, n - 1, idx, val); }

    private void update(int node, int start, int end, int idx, int val) {
        if (start == end) { tree[node] = val; return; }
        int mid = (start + end) / 2;
        if (idx <= mid) update(node * 2, start, mid, idx, val);
        else update(node * 2 + 1, mid + 1, end, idx, val);
        tree[node] = tree[node * 2] + tree[node * 2 + 1];
    }

    public int query(int l, int r) { return query(1, 0, n - 1, l, r); }

    private int query(int node, int start, int end, int l, int r) {
        if (r < start || end < l) return 0;
        if (l <= start && end <= r) return tree[node];
        int mid = (start + end) / 2;
        return query(node * 2, start, mid, l, r) + query(node * 2 + 1, mid + 1, end, l, r);
    }

    public static void main(String[] args) {
        Problem01_RangeSumQueryMutable sol = new Problem01_RangeSumQueryMutable();
        int[] nums = {1, 3, 5, 7, 9, 11};
        sol.build(nums);
        System.out.println("Sum [1,3]: " + sol.query(1, 3)); // 15
        sol.update(1, 10);
        System.out.println("Sum [1,3] after update: " + sol.query(1, 3)); // 22
    }
}
