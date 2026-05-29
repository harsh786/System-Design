import java.util.*;

public class Problem17_BoruvkasAlgorithm {
    public int boruvkaMST(int n, int[][] edges) {
        int[] parent = new int[n]; for (int i = 0; i < n; i++) parent[i] = i;
        int cost = 0, components = n;
        while (components > 1) {
            int[] cheapest = new int[n]; Arrays.fill(cheapest, -1);
            for (int i = 0; i < edges.length; i++) {
                int u = find(parent, edges[i][0]), v = find(parent, edges[i][1]);
                if (u == v) continue;
                if (cheapest[u] == -1 || edges[i][2] < edges[cheapest[u]][2]) cheapest[u] = i;
                if (cheapest[v] == -1 || edges[i][2] < edges[cheapest[v]][2]) cheapest[v] = i;
            }
            for (int i = 0; i < n; i++) {
                if (cheapest[i] != -1) {
                    int u = find(parent, edges[cheapest[i]][0]), v = find(parent, edges[cheapest[i]][1]);
                    if (u != v) { parent[u] = v; cost += edges[cheapest[i]][2]; components--; }
                }
            }
        }
        return cost;
    }
    private int find(int[] p, int x) { return p[x] == x ? x : (p[x] = find(p, p[x])); }

    public static void main(String[] args) {
        Problem17_BoruvkasAlgorithm sol = new Problem17_BoruvkasAlgorithm();
        System.out.println(sol.boruvkaMST(4, new int[][]{{0,1,1},{0,2,4},{1,2,2},{1,3,5},{2,3,3}})); // 6
    }
}
