package segmenttree;

/**
 * Problem 39: K-th Order Statistic Segment Tree
 * 
 * Approach: Segment tree on value range counting occurrences. Walk tree to find k-th smallest.
 * 
 * Time Complexity: O(log m) per operation where m is value range
 * Space Complexity: O(m)
 */
public class Problem39_KthOrderStatisticSegmentTree {
    
    private int[] tree;
    private int size;
    
    public Problem39_KthOrderStatisticSegmentTree(int maxVal) {
        size = maxVal + 1;
        tree = new int[4 * size];
    }
    
    public void insert(int val) { update(1, 0, size - 1, val, 1); }
    public void remove(int val) { update(1, 0, size - 1, val, -1); }
    
    private void update(int o, int s, int e, int idx, int delta) {
        if (s == e) { tree[o] += delta; return; }
        int mid = (s + e) / 2;
        if (idx <= mid) update(2 * o, s, mid, idx, delta);
        else update(2 * o + 1, mid + 1, e, idx, delta);
        tree[o] = tree[2 * o] + tree[2 * o + 1];
    }
    
    // Find k-th smallest (1-indexed)
    public int kth(int k) { return kth(1, 0, size - 1, k); }
    
    private int kth(int o, int s, int e, int k) {
        if (s == e) return s;
        int mid = (s + e) / 2;
        if (tree[2 * o] >= k) return kth(2 * o, s, mid, k);
        return kth(2 * o + 1, mid + 1, e, k - tree[2 * o]);
    }
    
    public int count() { return tree[1]; }
    
    public static void main(String[] args) {
        Problem39_KthOrderStatisticSegmentTree st = new Problem39_KthOrderStatisticSegmentTree(100);
        st.insert(5); st.insert(3); st.insert(8); st.insert(1); st.insert(7);
        System.out.println(st.kth(1)); // 1
        System.out.println(st.kth(3)); // 5
        System.out.println(st.kth(5)); // 8
        st.remove(3);
        System.out.println(st.kth(2)); // 5
    }
}
