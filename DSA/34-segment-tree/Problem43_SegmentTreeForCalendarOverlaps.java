package segmenttree;

/**
 * Problem 43: Segment Tree for Calendar Overlaps (find max overlap count)
 * 
 * Approach: Segment tree with lazy range add and global max query.
 * Each booking adds 1 to [start, end-1]. Max overlap = max value in tree.
 * 
 * Time Complexity: O(log n) per booking
 * Space Complexity: O(n)
 */
public class Problem43_SegmentTreeForCalendarOverlaps {
    
    private int[] tree, lazy;
    private int N;
    
    public Problem43_SegmentTreeForCalendarOverlaps(int maxTime) {
        N = maxTime;
        tree = new int[4 * N]; lazy = new int[4 * N];
    }
    
    private void pushDown(int o) {
        if (lazy[o] != 0) {
            tree[2*o] += lazy[o]; lazy[2*o] += lazy[o];
            tree[2*o+1] += lazy[o]; lazy[2*o+1] += lazy[o];
            lazy[o] = 0;
        }
    }
    
    public void book(int l, int r) { update(1, 0, N - 1, l, r - 1, 1); }
    
    private void update(int o, int s, int e, int l, int r, int val) {
        if (r < s || e < l) return;
        if (l <= s && e <= r) { tree[o] += val; lazy[o] += val; return; }
        pushDown(o);
        int mid = (s + e) / 2;
        update(2*o, s, mid, l, r, val); update(2*o+1, mid+1, e, l, r, val);
        tree[o] = Math.max(tree[2*o], tree[2*o+1]);
    }
    
    public int maxOverlap() { return tree[1]; }
    
    public static void main(String[] args) {
        Problem43_SegmentTreeForCalendarOverlaps cal = new Problem43_SegmentTreeForCalendarOverlaps(100);
        cal.book(10, 20); System.out.println(cal.maxOverlap()); // 1
        cal.book(15, 30); System.out.println(cal.maxOverlap()); // 2
        cal.book(12, 18); System.out.println(cal.maxOverlap()); // 3
    }
}
