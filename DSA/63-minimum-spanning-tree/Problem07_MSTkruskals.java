import java.util.*;

public class Problem07_MSTkruskals {
    public int kruskalMST(int n, int[][] edges) {
        Arrays.sort(edges, (a,b) -> a[2]-b[2]);
        int[] parent = new int[n]; for (int i = 0; i < n; i++) parent[i] = i;
        int cost = 0, count = 0;
        for (int[] e : edges) {
            int u = find(parent, e[0]), v = find(parent, e[1]);
            if (u != v) { parent[u] = v; cost += e[2]; if (++count == n-1) break; }
        }
        return cost;
    }

    private int find(int[] p, int x) { return p[x] == x ? x : (p[x] = find(p, p[x])); }

    public static void main(String[] args) {
        Problem07_MSTkruskals sol = new Problem07_MSTkruskals();
        System.out.println(sol.kruskalMST(4, new int[][]{{0,1,1},{0,2,4},{1,2,2},{1,3,5},{2,3,3}})); // 6
    }
}
