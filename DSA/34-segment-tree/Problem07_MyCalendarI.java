/**
 * Problem 7: My Calendar I (LeetCode 729)
 * Approach: Segment tree with lazy propagation to mark booked intervals.
 * Query if any point in [start, end-1] is booked before booking.
 * Time: O(log C) per operation where C is coordinate range
 * Space: O(n log C)
 * Production Analogy: Meeting room booking system preventing double-bookings.
 */
import java.util.*;

public class Problem07_MyCalendarI {
    Map<Integer, int[]> tree = new HashMap<>(); // node -> [max, lazy]

    private int[] get(int node) {
        return tree.computeIfAbsent(node, k -> new int[2]);
    }

    private void push(int node) {
        int[] nd = get(node);
        if (nd[1] > 0) {
            int[] left = get(node * 2), right = get(node * 2 + 1);
            left[0] = Math.max(left[0], nd[1]); left[1] = Math.max(left[1], nd[1]);
            right[0] = Math.max(right[0], nd[1]); right[1] = Math.max(right[1], nd[1]);
            nd[1] = 0;
        }
    }

    private void update(int node, int s, int e, int l, int r) {
        if (r < s || e < l) return;
        int[] nd = get(node);
        if (l <= s && e <= r) { nd[0] = 1; nd[1] = 1; return; }
        push(node);
        int m = (s + e) / 2;
        update(node * 2, s, m, l, r);
        update(node * 2 + 1, m + 1, e, l, r);
        nd[0] = Math.max(get(node * 2)[0], get(node * 2 + 1)[0]);
    }

    private int query(int node, int s, int e, int l, int r) {
        if (r < s || e < l) return 0;
        int[] nd = get(node);
        if (l <= s && e <= r) return nd[0];
        push(node);
        int m = (s + e) / 2;
        return Math.max(query(node * 2, s, m, l, r), query(node * 2 + 1, m + 1, e, l, r));
    }

    public boolean book(int start, int end) {
        if (query(1, 0, 1_000_000_000, start, end - 1) > 0) return false;
        update(1, 0, 1_000_000_000, start, end - 1);
        return true;
    }

    public static void main(String[] args) {
        Problem07_MyCalendarI cal = new Problem07_MyCalendarI();
        System.out.println(cal.book(10, 20)); // true
        System.out.println(cal.book(15, 25)); // false
        System.out.println(cal.book(20, 30)); // true
    }
}
