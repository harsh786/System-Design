import java.util.*;

public class Problem05_CriticalPseudoCriticalEdges {
    public List<List<Integer>> findCriticalAndPseudoCriticalEdges(int n, int[][] edges) {
        int m = edges.length;
        int[][] indexed = new int[m][4];
        for (int i = 0; i < m; i++) { indexed[i] = new int[]{edges[i][0], edges[i][1], edges[i][2], i}; }
        Arrays.sort(indexed, (a,b) -> a[2]-b[2]);
        int mstWeight = kruskal(n, indexed, -1, -1);
        List<Integer> critical = new ArrayList<>(), pseudo = new ArrayList<>();
        for (int i = 0; i < m; i++) {
            if (kruskal(n, indexed, i, -1) > mstWeight) critical.add(indexed[i][3]);
            else if (kruskal(n, indexed, -1, i) == mstWeight) pseudo.add(indexed[i][3]);
        }
        return Arrays.asList(critical, pseudo);
    }

    private int kruskal(int n, int[][] edges, int exclude, int include) {
        int[] parent = new int[n]; for (int i = 0; i < n; i++) parent[i] = i;
        int cost = 0, count = 0;
        if (include != -1) { union(parent, edges[include][0], edges[include][1]); cost += edges[include][2]; count++; }
        for (int i = 0; i < edges.length; i++) {
            if (i == exclude) continue;
            int u = find(parent, edges[i][0]), v = find(parent, edges[i][1]);
            if (u != v) { parent[u] = v; cost += edges[i][2]; count++; }
        }
        return count == n-1 ? cost : Integer.MAX_VALUE;
    }

    private void union(int[] p, int a, int b) { p[find(p,a)] = find(p,b); }
    private int find(int[] p, int x) { return p[x] == x ? x : (p[x] = find(p, p[x])); }

    public static void main(String[] args) {
        Problem05_CriticalPseudoCriticalEdges sol = new Problem05_CriticalPseudoCriticalEdges();
        System.out.println(sol.findCriticalAndPseudoCriticalEdges(5, new int[][]{{0,1,1},{1,2,1},{2,3,2},{0,3,2},{0,4,3},{3,4,3},{1,4,6}}));
    }
}
