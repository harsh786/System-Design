/**
 * Problem 5: Reverse Pairs (LeetCode 493)
 * Approach: Segment tree on coordinate-compressed values. For each element,
 * query count of elements > 2*nums[i] already inserted, then insert nums[i].
 * Time: O(n log n)
 * Space: O(n)
 * Production Analogy: Detecting anomalous transactions where amount exceeds 2x any subsequent one.
 */
import java.util.*;

public class Problem05_ReversePairs {
    int[] tree;

    private void update(int node, int s, int e, int idx) {
        if (s == e) { tree[node]++; return; }
        int m = (s + e) / 2;
        if (idx <= m) update(node * 2, s, m, idx);
        else update(node * 2 + 1, m + 1, e, idx);
        tree[node] = tree[node * 2] + tree[node * 2 + 1];
    }

    private int query(int node, int s, int e, int l, int r) {
        if (l > r || r < s || e < l) return 0;
        if (l <= s && e <= r) return tree[node];
        int m = (s + e) / 2;
        return query(node * 2, s, m, l, r) + query(node * 2 + 1, m + 1, e, l, r);
    }

    public int reversePairs(int[] nums) {
        TreeSet<Long> set = new TreeSet<>();
        for (int v : nums) { set.add((long) v); set.add(2L * v); }
        Map<Long, Integer> rank = new HashMap<>();
        int r = 0;
        for (long v : set) rank.put(v, r++);

        tree = new int[4 * r];
        int count = 0;
        for (int v : nums) {
            int idx2 = rank.get(2L * v);
            count += query(1, 0, r - 1, idx2 + 1, r - 1);
            update(1, 0, r - 1, rank.get((long) v));
        }
        return count;
    }

    public static void main(String[] args) {
        Problem05_ReversePairs sol = new Problem05_ReversePairs();
        System.out.println(sol.reversePairs(new int[]{1, 3, 2, 3, 1})); // 2
    }
}
