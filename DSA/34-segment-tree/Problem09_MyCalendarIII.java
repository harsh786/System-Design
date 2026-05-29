/**
 * Problem 9: My Calendar III (LeetCode 732)
 * Approach: Segment tree with lazy propagation tracking max overlap.
 * Each book adds 1 to range, return global max.
 * Time: O(log C) per operation
 * Space: O(n log C)
 * Production Analogy: Finding peak concurrent users across all time intervals.
 */
import java.util.*;

public class Problem09_MyCalendarIII {
    Map<Integer, int[]> tree = new HashMap<>();

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

    public int book(int start, int end) {
        update(1, 0, 1_000_000_000, start, end - 1);
        return get(1)[0];
    }

    public static void main(String[] args) {
        Problem09_MyCalendarIII cal = new Problem09_MyCalendarIII();
        System.out.println(cal.book(10, 20)); // 1
        System.out.println(cal.book(50, 60)); // 1
        System.out.println(cal.book(10, 40)); // 2
        System.out.println(cal.book(5, 15));  // 3
    }
}
