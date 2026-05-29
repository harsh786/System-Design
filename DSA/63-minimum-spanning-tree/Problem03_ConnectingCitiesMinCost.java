import java.util.*;

public class Problem03_ConnectingCitiesMinCost {
    public int minimumCost(int n, int[][] connections) {
        Arrays.sort(connections, (a,b) -> a[2]-b[2]);
        int[] parent = new int[n+1]; for (int i = 0; i <= n; i++) parent[i] = i;
        int cost = 0, edges = 0;
        for (int[] c : connections) {
            int u = find(parent, c[0]), v = find(parent, c[1]);
            if (u != v) { parent[u] = v; cost += c[2]; edges++; }
        }
        return edges == n-1 ? cost : -1;
    }

    private int find(int[] p, int x) { return p[x] == x ? x : (p[x] = find(p, p[x])); }

    public static void main(String[] args) {
        Problem03_ConnectingCitiesMinCost sol = new Problem03_ConnectingCitiesMinCost();
        System.out.println(sol.minimumCost(3, new int[][]{{1,2,5},{1,3,6},{2,3,1}})); // 6
    }
}
