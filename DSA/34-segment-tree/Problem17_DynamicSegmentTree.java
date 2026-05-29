package segmenttree;

/**
 * Problem 17: Dynamic Segment Tree (Pointer-based, no pre-allocation)
 * 
 * Approach: Create nodes on demand. Useful when range is huge (e.g., 1e9) but updates are sparse.
 * 
 * Time Complexity: O(log R) per operation where R is the range
 * Space Complexity: O(Q log R) where Q is number of updates
 */
public class Problem17_DynamicSegmentTree {
    
    static class Node {
        long val;
        Node left, right;
    }
    
    private Node root = new Node();
    private int lo, hi;
    
    public Problem17_DynamicSegmentTree(int lo, int hi) { this.lo = lo; this.hi = hi; }
    
    public void update(int idx, long val) { update(root, lo, hi, idx, val); }
    
    private void update(Node node, int s, int e, int idx, long val) {
        if (s == e) { node.val += val; return; }
        int mid = s + (e - s) / 2;
        if (idx <= mid) {
            if (node.left == null) node.left = new Node();
            update(node.left, s, mid, idx, val);
        } else {
            if (node.right == null) node.right = new Node();
            update(node.right, mid + 1, e, idx, val);
        }
        node.val = (node.left != null ? node.left.val : 0) + (node.right != null ? node.right.val : 0);
    }
    
    public long query(int l, int r) { return query(root, lo, hi, l, r); }
    
    private long query(Node node, int s, int e, int l, int r) {
        if (node == null || r < s || e < l) return 0;
        if (l <= s && e <= r) return node.val;
        int mid = s + (e - s) / 2;
        return query(node.left, s, mid, l, r) + query(node.right, mid + 1, e, l, r);
    }
    
    public static void main(String[] args) {
        Problem17_DynamicSegmentTree st = new Problem17_DynamicSegmentTree(0, 1_000_000_000);
        st.update(100, 5);
        st.update(999_999_999, 10);
        st.update(500_000_000, 3);
        System.out.println(st.query(0, 1_000_000_000));   // 18
        System.out.println(st.query(100, 100));            // 5
        System.out.println(st.query(101, 999_999_998));    // 3
    }
}
