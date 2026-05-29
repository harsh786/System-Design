import java.util.*;

public class Problem04_OptimizeWaterDistribution {
    /* Add virtual node 0 with edges to each house = well cost, then find MST */
    public int minCostToSupplyWater(int n, int[] wells, int[][] pipes) {
        List<int[]> edges = new ArrayList<>();
        for (int i = 0; i < n; i++) edges.add(new int[]{wells[i], 0, i+1});
        for (int[] p : pipes) edges.add(new int[]{p[2], p[0], p[1]});
        edges.sort((a,b) -> a[0]-b[0]);
        int[] parent = new int[n+1]; for (int i = 0; i <= n; i++) parent[i] = i;
        int cost = 0;
        for (int[] e : edges) {
            int u = find(parent, e[1]), v = find(parent, e[2]);
            if (u != v) { parent[u] = v; cost += e[0]; }
        }
        return cost;
    }

    private int find(int[] p, int x) { return p[x] == x ? x : (p[x] = find(p, p[x])); }

    public static void main(String[] args) {
        Problem04_OptimizeWaterDistribution sol = new Problem04_OptimizeWaterDistribution();
        System.out.println(sol.minCostToSupplyWater(3, new int[]{1,2,2}, new int[][]{{1,2,1},{2,3,1}})); // 3
    }
}
