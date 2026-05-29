import java.util.*;

public class Problem13_NetworkDesignMinCost {
    public int networkDesign(int n, int[][] connections) {
        Arrays.sort(connections, (a,b) -> a[2]-b[2]);
        int[] parent = new int[n]; for (int i = 0; i < n; i++) parent[i] = i;
        int cost = 0, edges = 0;
        for (int[] c : connections) {
            int u = find(parent, c[0]), v = find(parent, c[1]);
            if (u != v) { parent[u] = v; cost += c[2]; edges++; }
        }
        return edges == n-1 ? cost : -1;
    }
    private int find(int[] p, int x) { return p[x] == x ? x : (p[x] = find(p, p[x])); }

    public static void main(String[] args) {
        Problem13_NetworkDesignMinCost sol = new Problem13_NetworkDesignMinCost();
        System.out.println(sol.networkDesign(5, new int[][]{{0,1,2},{1,2,3},{2,3,4},{3,4,5},{0,4,10},{0,2,6}}));
    }
}
