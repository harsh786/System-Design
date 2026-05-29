/**
 * Problem 11: Range Module (LeetCode 715)
 * Approach: Dynamic segment tree with lazy propagation for range assign (0/1).
 * Time: O(log C) per operation
 * Space: O(n log C)
 * Production Analogy: IP address range allocation tracking which ranges are assigned.
 */
import java.util.*;

public class Problem11_RangeModule {
    Map<Integer, int[]> nodes = new HashMap<>(); // [val, lazy] lazy: -1=none,0=remove,1=add

    private int[] get(int n) { return nodes.computeIfAbsent(n, k -> new int[]{0, -1}); }

    private void push(int node, int s, int e) {
        int[] nd = get(node);
        if (nd[1] != -1) {
            int m = (s + e) / 2;
            int[] l = get(node*2), r = get(node*2+1);
            l[0] = nd[1] * (m - s + 1); l[1] = nd[1];
            r[0] = nd[1] * (e - m); r[1] = nd[1];
            nd[1] = -1;
        }
    }

    private void update(int node, int s, int e, int l, int r, int val) {
        if (r < s || e < l) return;
        int[] nd = get(node);
        if (l <= s && e <= r) { nd[0] = val * (e - s + 1); nd[1] = val; return; }
        push(node, s, e);
        int m = (s + e) / 2;
        update(node*2, s, m, l, r, val);
        update(node*2+1, m+1, e, l, r, val);
        nd[0] = get(node*2)[0] + get(node*2+1)[0];
    }

    private int query(int node, int s, int e, int l, int r) {
        if (r < s || e < l) return 0;
        int[] nd = get(node);
        if (l <= s && e <= r) return nd[0];
        push(node, s, e);
        int m = (s + e) / 2;
        return query(node*2, s, m, l, r) + query(node*2+1, m+1, e, l, r);
    }

    static final int MAX = 1_000_000_000;

    public void addRange(int left, int right) { update(1, 0, MAX, left, right - 1, 1); }
    public boolean queryRange(int left, int right) { return query(1, 0, MAX, left, right - 1) == right - left; }
    public void removeRange(int left, int right) { update(1, 0, MAX, left, right - 1, 0); }

    public static void main(String[] args) {
        Problem11_RangeModule rm = new Problem11_RangeModule();
        rm.addRange(10, 20);
        rm.removeRange(14, 16);
        System.out.println(rm.queryRange(10, 14)); // true
        System.out.println(rm.queryRange(13, 15)); // false
    }
}
