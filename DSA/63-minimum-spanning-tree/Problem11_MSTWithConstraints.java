import java.util.*;

public class Problem11_MSTWithConstraints {
    /* MST where certain edges must be included */
    public int mstWithRequired(int n, int[][] edges, int[][] required) {
        int[] parent = new int[n]; for (int i = 0; i < n; i++) parent[i] = i;
        int cost = 0;
        for (int[] r : required) { union(parent, r[0], r[1]); cost += r[2]; }
        Arrays.sort(edges, (a,b) -> a[2]-b[2]);
        for (int[] e : edges) {
            int u = find(parent, e[0]), v = find(parent, e[1]);
            if (u != v) { parent[u] = v; cost += e[2]; }
        }
        return cost;
    }
    private void union(int[] p, int a, int b) { p[find(p,a)] = find(p,b); }
    private int find(int[] p, int x) { return p[x] == x ? x : (p[x] = find(p, p[x])); }

    public static void main(String[] args) {
        Problem11_MSTWithConstraints sol = new Problem11_MSTWithConstraints();
        System.out.println(sol.mstWithRequired(4, new int[][]{{0,1,1},{0,2,4},{1,2,2},{1,3,5},{2,3,3}}, new int[][]{{0,2,4}}));
    }
}
