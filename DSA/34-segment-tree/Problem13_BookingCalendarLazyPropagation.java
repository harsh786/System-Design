package segmenttree;

/**
 * Problem 13: Booking Calendar with Lazy Propagation
 * 
 * Approach: Segment tree with lazy propagation to support range add and range max query
 * for booking overlap detection.
 * 
 * Time Complexity: O(log n) per book operation
 * Space Complexity: O(n)
 */
public class Problem13_BookingCalendarLazyPropagation {
    
    private int[] tree, lazy;
    private int N = 1000001;
    
    public Problem13_BookingCalendarLazyPropagation() {
        tree = new int[4 * N];
        lazy = new int[4 * N];
    }
    
    private void pushDown(int node) {
        if (lazy[node] != 0) {
            tree[2 * node] += lazy[node];
            tree[2 * node + 1] += lazy[node];
            lazy[2 * node] += lazy[node];
            lazy[2 * node + 1] += lazy[node];
            lazy[node] = 0;
        }
    }
    
    private void update(int node, int start, int end, int l, int r, int val) {
        if (r < start || end < l) return;
        if (l <= start && end <= r) {
            tree[node] += val;
            lazy[node] += val;
            return;
        }
        pushDown(node);
        int mid = (start + end) / 2;
        update(2 * node, start, mid, l, r, val);
        update(2 * node + 1, mid + 1, end, l, r, val);
        tree[node] = Math.max(tree[2 * node], tree[2 * node + 1]);
    }
    
    private int query(int node, int start, int end, int l, int r) {
        if (r < start || end < l) return 0;
        if (l <= start && end <= r) return tree[node];
        pushDown(node);
        int mid = (start + end) / 2;
        return Math.max(query(2 * node, start, mid, l, r), query(2 * node + 1, mid + 1, end, l, r));
    }
    
    public boolean book(int start, int end, int maxAllowed) {
        int cur = query(1, 0, N - 1, start, end - 1);
        if (cur >= maxAllowed) return false;
        update(1, 0, N - 1, start, end - 1, 1);
        return true;
    }
    
    public static void main(String[] args) {
        Problem13_BookingCalendarLazyPropagation cal = new Problem13_BookingCalendarLazyPropagation();
        System.out.println(cal.book(10, 20, 3)); // true
        System.out.println(cal.book(15, 25, 3)); // true
        System.out.println(cal.book(12, 22, 3)); // true
        System.out.println(cal.book(14, 18, 3)); // false (would be 4th overlap)
    }
}
