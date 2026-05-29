package segmenttree;

/**
 * Problem 30: Segment Tree for GCD (Range GCD Query with Point Updates)
 * 
 * Time Complexity: O(log n * log(max_val)) per operation
 * Space Complexity: O(n)
 */
public class Problem30_SegmentTreeForGCD {
    
    private int[] tree;
    private int n;
    
    public Problem30_SegmentTreeForGCD(int[] arr) {
        n = arr.length; tree = new int[4 * n];
        build(1, 0, n - 1, arr);
    }
    
    private int gcd(int a, int b) { return b == 0 ? a : gcd(b, a % b); }
    
    private void build(int node, int s, int e, int[] arr) {
        if (s == e) { tree[node] = arr[s]; return; }
        int mid = (s + e) / 2;
        build(2 * node, s, mid, arr); build(2 * node + 1, mid + 1, e, arr);
        tree[node] = gcd(tree[2 * node], tree[2 * node + 1]);
    }
    
    public void update(int idx, int val) { update(1, 0, n - 1, idx, val); }
    
    private void update(int node, int s, int e, int idx, int val) {
        if (s == e) { tree[node] = val; return; }
        int mid = (s + e) / 2;
        if (idx <= mid) update(2 * node, s, mid, idx, val);
        else update(2 * node + 1, mid + 1, e, idx, val);
        tree[node] = gcd(tree[2 * node], tree[2 * node + 1]);
    }
    
    public int query(int l, int r) { return query(1, 0, n - 1, l, r); }
    
    private int query(int node, int s, int e, int l, int r) {
        if (r < s || e < l) return 0;
        if (l <= s && e <= r) return tree[node];
        int mid = (s + e) / 2;
        return gcd(query(2 * node, s, mid, l, r), query(2 * node + 1, mid + 1, e, l, r));
    }
    
    public static void main(String[] args) {
        Problem30_SegmentTreeForGCD st = new Problem30_SegmentTreeForGCD(new int[]{12, 18, 24, 36, 60});
        System.out.println(st.query(0, 4)); // 6
        System.out.println(st.query(2, 4)); // 12
        st.update(2, 15);
        System.out.println(st.query(0, 4)); // 3
    }
}
