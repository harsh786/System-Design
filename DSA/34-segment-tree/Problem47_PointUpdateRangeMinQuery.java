package segmenttree;

/**
 * Problem 47: Point Update Range Min Query
 * 
 * Time Complexity: O(log n) per operation
 * Space Complexity: O(n)
 */
public class Problem47_PointUpdateRangeMinQuery {
    
    private int[] tree;
    private int n;
    
    public Problem47_PointUpdateRangeMinQuery(int[] arr) {
        n = arr.length; tree = new int[4 * n];
        java.util.Arrays.fill(tree, Integer.MAX_VALUE);
        build(1, 0, n-1, arr);
    }
    
    private void build(int o, int s, int e, int[] arr) {
        if (s == e) { tree[o] = arr[s]; return; }
        int mid = (s+e)/2;
        build(2*o, s, mid, arr); build(2*o+1, mid+1, e, arr);
        tree[o] = Math.min(tree[2*o], tree[2*o+1]);
    }
    
    public void update(int idx, int val) { update(1, 0, n-1, idx, val); }
    
    private void update(int o, int s, int e, int idx, int val) {
        if (s == e) { tree[o] = val; return; }
        int mid = (s+e)/2;
        if (idx <= mid) update(2*o, s, mid, idx, val);
        else update(2*o+1, mid+1, e, idx, val);
        tree[o] = Math.min(tree[2*o], tree[2*o+1]);
    }
    
    public int query(int l, int r) { return query(1, 0, n-1, l, r); }
    
    private int query(int o, int s, int e, int l, int r) {
        if (r < s || e < l) return Integer.MAX_VALUE;
        if (l <= s && e <= r) return tree[o];
        int mid = (s+e)/2;
        return Math.min(query(2*o, s, mid, l, r), query(2*o+1, mid+1, e, l, r));
    }
    
    public static void main(String[] args) {
        Problem47_PointUpdateRangeMinQuery st = new Problem47_PointUpdateRangeMinQuery(new int[]{5,2,8,1,9,3});
        System.out.println(st.query(0, 5)); // 1
        System.out.println(st.query(0, 2)); // 2
        st.update(3, 10);
        System.out.println(st.query(0, 5)); // 2
    }
}
