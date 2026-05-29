/**
 * Problem 8: My Calendar II (LeetCode 731)
 * Approach: Segment tree tracking max overlap count. Book only if max in range < 2.
 * Time: O(log C) per operation
 * Space: O(n log C)
 * Production Analogy: Conference room allowing at most 2 overlapping events.
 */
import java.util.*;

public class Problem08_MyCalendarII {
    Map<Integer, int[]> tree = new HashMap<>(); // [max, lazy_add]

    private int[] get(int node) { return tree.computeIfAbsent(node, k -> new int[2]); }

    private void push(int node) {
        int[] nd = get(node);
        if (nd[1] > 0) {
            for (int c : new int[]{node * 2, node * 2 + 1}) {
                int[] child = get(c);
                child[0] += nd[1]; child[1] += nd[1];
            }
            nd[1] = 0;
        }
    }

    private void update(int node, int s, int e, int l, int r) {
        if (r < s || e < l) return;
        int[] nd = get(node);
        if (l <= s && e <= r) { nd[0]++; nd[1]++; return; }
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
        if (query(1, 0, 1_000_000_000, start, end - 1) >= 2) return false;
        update(1, 0, 1_000_000_000, start, end - 1);
        return true;
    }

    public static void main(String[] args) {
        Problem08_MyCalendarII cal = new Problem08_MyCalendarII();
        System.out.println(cal.book(10, 20)); // true
        System.out.println(cal.book(50, 60)); // true
        System.out.println(cal.book(10, 40)); // true
        System.out.println(cal.book(5, 15));  // false (triple booking)
    }
}
