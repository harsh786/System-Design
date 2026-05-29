/**
 * Problem 4: Count of Smaller Numbers After Self (LeetCode 315)
 * Approach: Process from right to left, use segment tree on value range to count elements
 * smaller than current. Coordinate compress values first.
 * Time: O(n log n)
 * Space: O(n)
 * Production Analogy: Real-time leaderboard counting how many players scored below a threshold.
 */
import java.util.*;

public class Problem04_CountSmallerNumbersAfterSelf {
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

    public List<Integer> countSmaller(int[] nums) {
        int n = nums.length;
        int[] sorted = nums.clone();
        Arrays.sort(sorted);
        Map<Integer, Integer> rank = new HashMap<>();
        int r = 0;
        for (int v : sorted) if (!rank.containsKey(v)) rank.put(v, r++);

        tree = new int[4 * r];
        Integer[] result = new Integer[n];
        for (int i = n - 1; i >= 0; i--) {
            int idx = rank.get(nums[i]);
            result[i] = query(1, 0, r - 1, 0, idx - 1);
            update(1, 0, r - 1, idx);
        }
        return Arrays.asList(result);
    }

    public static void main(String[] args) {
        Problem04_CountSmallerNumbersAfterSelf sol = new Problem04_CountSmallerNumbersAfterSelf();
        System.out.println(sol.countSmaller(new int[]{5, 2, 6, 1})); // [2,1,1,0]
    }
}
