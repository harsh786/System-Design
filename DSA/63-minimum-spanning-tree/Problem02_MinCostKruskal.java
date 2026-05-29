import java.util.*;

public class Problem02_MinCostKruskal {
    public int minCostConnectPoints(int[][] points) {
        int n = points.length;
        List<int[]> edges = new ArrayList<>();
        for (int i = 0; i < n; i++) for (int j = i+1; j < n; j++)
            edges.add(new int[]{Math.abs(points[i][0]-points[j][0])+Math.abs(points[i][1]-points[j][1]), i, j});
        edges.sort((a,b) -> a[0]-b[0]);
        int[] parent = new int[n]; for (int i = 0; i < n; i++) parent[i] = i;
        int cost = 0, count = 0;
        for (int[] e : edges) {
            int u = find(parent, e[1]), v = find(parent, e[2]);
            if (u != v) { parent[u] = v; cost += e[0]; if (++count == n-1) break; }
        }
        return cost;
    }

    private int find(int[] p, int x) { return p[x] == x ? x : (p[x] = find(p, p[x])); }

    public static void main(String[] args) {
        Problem02_MinCostKruskal sol = new Problem02_MinCostKruskal();
        System.out.println(sol.minCostConnectPoints(new int[][]{{0,0},{2,2},{3,10},{5,2},{7,0}})); // 20
    }
}
