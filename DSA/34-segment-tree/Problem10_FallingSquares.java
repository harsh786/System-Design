/**
 * Problem 10: Falling Squares (LeetCode 699)
 * Approach: Coordinate compress, segment tree with lazy for range max update.
 * For each square, query max height in range, then update range to height + sideLength.
 * Time: O(n log n)
 * Space: O(n)
 * Production Analogy: Stacking containers in a warehouse, tracking max height at each position.
 */
import java.util.*;

public class Problem10_FallingSquares {
    int[] tree, lazy;

    private void push(int node) {
        if (lazy[node] > 0) {
            tree[node*2] = Math.max(tree[node*2], lazy[node]);
            tree[node*2+1] = Math.max(tree[node*2+1], lazy[node]);
            lazy[node*2] = Math.max(lazy[node*2], lazy[node]);
            lazy[node*2+1] = Math.max(lazy[node*2+1], lazy[node]);
            lazy[node] = 0;
        }
    }

    private void update(int node, int s, int e, int l, int r, int val) {
        if (r < s || e < l) return;
        if (l <= s && e <= r) { tree[node] = Math.max(tree[node], val); lazy[node] = Math.max(lazy[node], val); return; }
        push(node);
        int m = (s + e) / 2;
        update(node*2, s, m, l, r, val);
        update(node*2+1, m+1, e, l, r, val);
        tree[node] = Math.max(tree[node*2], tree[node*2+1]);
    }

    private int query(int node, int s, int e, int l, int r) {
        if (r < s || e < l) return 0;
        if (l <= s && e <= r) return tree[node];
        push(node);
        int m = (s + e) / 2;
        return Math.max(query(node*2, s, m, l, r), query(node*2+1, m+1, e, l, r));
    }

    public List<Integer> fallingSquares(int[][] positions) {
        TreeSet<Integer> coords = new TreeSet<>();
        for (int[] p : positions) { coords.add(p[0]); coords.add(p[0] + p[1] - 1); }
        Map<Integer, Integer> idx = new HashMap<>();
        int i = 0;
        for (int c : coords) idx.put(c, i++);

        int n = coords.size();
        tree = new int[4 * n]; lazy = new int[4 * n];
        List<Integer> res = new ArrayList<>();
        int maxH = 0;
        for (int[] p : positions) {
            int l = idx.get(p[0]), r = idx.get(p[0] + p[1] - 1);
            int h = query(1, 0, n-1, l, r) + p[1];
            update(1, 0, n-1, l, r, h);
            maxH = Math.max(maxH, h);
            res.add(maxH);
        }
        return res;
    }

    public static void main(String[] args) {
        Problem10_FallingSquares sol = new Problem10_FallingSquares();
        System.out.println(sol.fallingSquares(new int[][]{{1,2},{2,3},{6,1}})); // [2,5,5]
    }
}
