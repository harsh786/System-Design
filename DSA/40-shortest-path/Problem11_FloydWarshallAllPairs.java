import java.util.*;

/**
 * Problem: Floyd-Warshall All Pairs Shortest Path
 *
 * Approach: DP - for each intermediate node k, update dist[i][j]
 *
 * Time Complexity: O(V^3)
 * Space Complexity: O(V^2)
 *
 * Production Analogy: Pre-computing all-pairs latency matrix for data center routing.
 */
public class Problem11_FloydWarshallAllPairs {

    public int[][] floydWarshall(int n, int[][] edges) {
        int INF = 100000;
        int[][] dist = new int[n][n];
        for (int[] row : dist) Arrays.fill(row, INF);
        for (int i = 0; i < n; i++) dist[i][i] = 0;
        for (int[] e : edges) dist[e[0]][e[1]] = e[2];

        for (int k = 0; k < n; k++)
            for (int i = 0; i < n; i++)
                for (int j = 0; j < n; j++)
                    dist[i][j] = Math.min(dist[i][j], dist[i][k] + dist[k][j]);
        return dist;
    }

    public static void main(String[] args) {
        Problem11_FloydWarshallAllPairs solver = new Problem11_FloydWarshallAllPairs();
        int[][] res = solver.floydWarshall(4, new int[][]{{0,1,3},{0,3,7},{1,2,2},{2,3,1}});
        System.out.println(Arrays.toString(res[0])); // [0,3,5,6]
    }
}
