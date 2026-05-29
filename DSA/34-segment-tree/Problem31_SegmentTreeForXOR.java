package segmenttree;

/**
 * Problem 31: Segment Tree for XOR (Range XOR Query with Point Updates)
 * 
 * Time Complexity: O(log n) per operation
 * Space Complexity: O(n)
 */
public class Problem31_SegmentTreeForXOR {
    
    private int[] tree;
    private int n;
    
    public Problem31_SegmentTreeForXOR(int[] arr) {
        n = arr.length; tree = new int[4 * n];
        build(1, 0, n - 1, arr);
    }
    
    private void build(int node, int s, int e, int[] arr) {
        if (s == e) { tree[node] = arr[s]; return; }
        int mid = (s + e) / 2;
        build(2 * node, s, mid, arr); build(2 * node + 1, mid + 1, e, arr);
        tree[node] = tree[2 * node] ^ tree[2 * node + 1];
    }
    
    public void update(int idx, int val) { update(1, 0, n - 1, idx, val); }
    
    private void update(int node, int s, int e, int idx, int val) {
        if (s == e) { tree[node] = val; return; }
        int mid = (s + e) / 2;
        if (idx <= mid) update(2 * node, s, mid, idx, val);
        else update(2 * node + 1, mid + 1, e, idx, val);
        tree[node] = tree[2 * node] ^ tree[2 * node + 1];
    }
    
    public int query(int l, int r) { return query(1, 0, n - 1, l, r); }
    
    private int query(int node, int s, int e, int l, int r) {
        if (r < s || e < l) return 0;
        if (l <= s && e <= r) return tree[node];
        int mid = (s + e) / 2;
        return query(2 * node, s, mid, l, r) ^ query(2 * node + 1, mid + 1, e, l, r);
    }
    
    public static void main(String[] args) {
        Problem31_SegmentTreeForXOR st = new Problem31_SegmentTreeForXOR(new int[]{1, 3, 5, 7, 9, 11});
        System.out.println(st.query(0, 5)); // 1^3^5^7^9^11 = 0
        System.out.println(st.query(1, 3)); // 3^5^7 = 1
        st.update(1, 4);
        System.out.println(st.query(1, 3)); // 4^5^7 = 6
    }
}
