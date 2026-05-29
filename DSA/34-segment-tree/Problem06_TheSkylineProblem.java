/**
 * Problem 6: The Skyline Problem (LeetCode 218)
 * Approach: Coordinate compress x-values, use segment tree with lazy propagation
 * to assign max heights over intervals, then sweep to extract key points.
 * Time: O(n log n)
 * Space: O(n)
 * Production Analogy: Rendering overlapping UI panels at different z-indices.
 */
import java.util.*;

public class Problem06_TheSkylineProblem {
    int[] tree, lazy;

    private void push(int node) {
        if (lazy[node] > 0) {
            tree[node * 2] = Math.max(tree[node * 2], lazy[node]);
            tree[node * 2 + 1] = Math.max(tree[node * 2 + 1], lazy[node]);
            lazy[node * 2] = Math.max(lazy[node * 2], lazy[node]);
            lazy[node * 2 + 1] = Math.max(lazy[node * 2 + 1], lazy[node]);
            lazy[node] = 0;
        }
    }

    private void update(int node, int s, int e, int l, int r, int val) {
        if (r < s || e < l) return;
        if (l <= s && e <= r) {
            tree[node] = Math.max(tree[node], val);
            lazy[node] = Math.max(lazy[node], val);
            return;
        }
        push(node);
        int m = (s + e) / 2;
        update(node * 2, s, m, l, r, val);
        update(node * 2 + 1, m + 1, e, l, r, val);
    }

    private int query(int node, int s, int e, int idx) {
        if (s == e) return tree[node];
        push(node);
        int m = (s + e) / 2;
        if (idx <= m) return query(node * 2, s, m, idx);
        else return query(node * 2 + 1, m + 1, e, idx);
    }

    public List<List<Integer>> getSkyline(int[][] buildings) {
        TreeSet<Integer> xs = new TreeSet<>();
        for (int[] b : buildings) { xs.add(b[0]); xs.add(b[1]); }
        List<Integer> sortedX = new ArrayList<>(xs);
        Map<Integer, Integer> xIdx = new HashMap<>();
        for (int i = 0; i < sortedX.size(); i++) xIdx.put(sortedX.get(i), i);

        int n = sortedX.size();
        tree = new int[4 * n];
        lazy = new int[4 * n];

        for (int[] b : buildings) {
            int l = xIdx.get(b[0]), r = xIdx.get(b[1]) - 1;
            if (l <= r) update(1, 0, n - 1, l, r, b[2]);
        }

        List<List<Integer>> result = new ArrayList<>();
        int prevH = 0;
        for (int i = 0; i < n; i++) {
            int h = query(1, 0, n - 1, i);
            if (h != prevH) {
                result.add(Arrays.asList(sortedX.get(i), h));
                prevH = h;
            }
        }
        return result;
    }

    public static void main(String[] args) {
        Problem06_TheSkylineProblem sol = new Problem06_TheSkylineProblem();
        int[][] buildings = {{2,9,10},{3,7,15},{5,12,12},{15,20,10},{19,24,8}};
        System.out.println(sol.getSkyline(buildings));
    }
}
