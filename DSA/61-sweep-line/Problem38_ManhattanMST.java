import java.util.*;

public class Problem38_ManhattanMST {
    /* Manhattan MST: for n points, only O(n) candidate edges needed via sweep line */
    public long manhattanMST(int[][] points) {
        int n = points.length;
        List<long[]> edges = new ArrayList<>();
        Integer[] idx = new Integer[n];
        for (int i = 0; i < n; i++) idx[i] = i;
        // For each of 4 rotations, find nearest neighbor in one octant
        for (int rot = 0; rot < 4; rot++) {
            Arrays.sort(idx, (a, b) -> (points[a][0] + points[a][1]) - (points[b][0] + points[b][1]));
            TreeMap<Integer, Integer> active = new TreeMap<>();
            for (int i = n - 1; i >= 0; i--) {
                int px = points[idx[i]][0], py = points[idx[i]][1];
                for (Map.Entry<Integer, Integer> e : active.tailMap(px - py).entrySet()) {
                    int j = e.getValue();
                    long dist = Math.abs((long)points[idx[i]][0]-points[j][0]) + Math.abs((long)points[idx[i]][1]-points[j][1]);
                    edges.add(new long[]{dist, idx[i], j});
                    break; // only nearest
                }
                active.put(px - py, idx[i]);
            }
            // rotate points
            for (int i = 0; i < n; i++) { int tmp = points[i][0]; points[i][0] = points[i][1]; points[i][1] = -tmp; }
        }
        // Kruskal
        edges.sort((a, b) -> Long.compare(a[0], b[0]));
        int[] parent = new int[n];
        for (int i = 0; i < n; i++) parent[i] = i;
        long total = 0; int count = 0;
        for (long[] e : edges) {
            int u = find(parent, (int)e[1]), v = find(parent, (int)e[2]);
            if (u != v) { parent[u] = v; total += e[0]; if (++count == n - 1) break; }
        }
        return total;
    }

    private int find(int[] p, int x) { return p[x] == x ? x : (p[x] = find(p, p[x])); }

    public static void main(String[] args) {
        Problem38_ManhattanMST sol = new Problem38_ManhattanMST();
        System.out.println(sol.manhattanMST(new int[][]{{0,0},{2,2},{3,10},{5,2},{7,0}}));
    }
}
