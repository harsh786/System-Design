package segmenttree;

/**
 * Problem 33: Segment Tree for First Greater Element (Walk on Segment Tree)
 * 
 * Approach: Find leftmost index in [l, r] where arr[i] >= val by walking the segment tree.
 * 
 * Time Complexity: O(log n) per query
 * Space Complexity: O(n)
 */
public class Problem33_SegmentTreeForFirstGreaterElement {
    
    private int[] tree;
    private int n;
    
    public Problem33_SegmentTreeForFirstGreaterElement(int[] arr) {
        n = arr.length; tree = new int[4 * n];
        build(1, 0, n - 1, arr);
    }
    
    private void build(int o, int s, int e, int[] arr) {
        if (s == e) { tree[o] = arr[s]; return; }
        int mid = (s + e) / 2;
        build(2 * o, s, mid, arr); build(2 * o + 1, mid + 1, e, arr);
        tree[o] = Math.max(tree[2 * o], tree[2 * o + 1]);
    }
    
    public void update(int idx, int val) { update(1, 0, n - 1, idx, val); }
    
    private void update(int o, int s, int e, int idx, int val) {
        if (s == e) { tree[o] = val; return; }
        int mid = (s + e) / 2;
        if (idx <= mid) update(2 * o, s, mid, idx, val);
        else update(2 * o + 1, mid + 1, e, idx, val);
        tree[o] = Math.max(tree[2 * o], tree[2 * o + 1]);
    }
    
    // Find leftmost index in [l, r] with value >= val, return -1 if none
    public int firstGreaterOrEqual(int l, int r, int val) { return query(1, 0, n - 1, l, r, val); }
    
    private int query(int o, int s, int e, int l, int r, int val) {
        if (r < s || e < l || tree[o] < val) return -1;
        if (s == e) return s;
        int mid = (s + e) / 2;
        int left = query(2 * o, s, mid, l, r, val);
        if (left != -1) return left;
        return query(2 * o + 1, mid + 1, e, l, r, val);
    }
    
    public static void main(String[] args) {
        Problem33_SegmentTreeForFirstGreaterElement st = new Problem33_SegmentTreeForFirstGreaterElement(new int[]{1, 3, 2, 5, 4, 7, 6});
        System.out.println(st.firstGreaterOrEqual(0, 6, 5)); // 3
        System.out.println(st.firstGreaterOrEqual(0, 2, 5)); // -1
        System.out.println(st.firstGreaterOrEqual(4, 6, 6)); // 5
    }
}
