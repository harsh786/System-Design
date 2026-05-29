import java.util.*;

public class Problem14_SteinerTree {
    /* Steiner Tree approximation: MST on required vertices using shortest paths */
    public int steinerTreeApprox(int n, int[][] edges, int[] required) {
        // Build distance matrix using Floyd-Warshall
        int[][] dist = new int[n][n];
        for (int[] r : dist) Arrays.fill(r, Integer.MAX_VALUE/2);
        for (int i = 0; i < n; i++) dist[i][i] = 0;
        for (int[] e : edges) { dist[e[0]][e[1]] = Math.min(dist[e[0]][e[1]], e[2]); dist[e[1]][e[0]] = Math.min(dist[e[1]][e[0]], e[2]); }
        for (int k = 0; k < n; k++) for (int i = 0; i < n; i++) for (int j = 0; j < n; j++)
            dist[i][j] = Math.min(dist[i][j], dist[i][k] + dist[k][j]);
        // MST on complete graph of required vertices
        int m = required.length;
        boolean[] inMST = new boolean[m];
        int[] key = new int[m]; Arrays.fill(key, Integer.MAX_VALUE);
        key[0] = 0; int cost = 0;
        for (int c = 0; c < m; c++) {
            int u = -1;
            for (int i = 0; i < m; i++) if (!inMST[i] && (u == -1 || key[i] < key[u])) u = i;
            inMST[u] = true; cost += key[u];
            for (int v = 0; v < m; v++) if (!inMST[v]) key[v] = Math.min(key[v], dist[required[u]][required[v]]);
        }
        return cost;
    }

    public static void main(String[] args) {
        Problem14_SteinerTree sol = new Problem14_SteinerTree();
        System.out.println(sol.steinerTreeApprox(5, new int[][]{{0,1,2},{1,2,3},{2,3,4},{3,4,5},{0,4,10},{1,3,1}}, new int[]{0,2,4}));
    }
}
