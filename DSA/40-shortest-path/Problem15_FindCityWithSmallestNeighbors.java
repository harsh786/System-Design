import java.util.*;

/**
 * Problem: Find the City With Smallest Number of Neighbors at Threshold Distance
 *
 * Approach: Floyd-Warshall then count reachable cities within threshold
 *
 * Time Complexity: O(V^3)
 * Space Complexity: O(V^2)
 *
 * Production Analogy: Finding the most isolated data center within latency SLA.
 */
public class Problem15_FindCityWithSmallestNeighbors {

    public int findTheCity(int n, int[][] edges, int distanceThreshold) {
        int INF = 100000;
        int[][] dist = new int[n][n];
        for (int[] row : dist) Arrays.fill(row, INF);
        for (int i = 0; i < n; i++) dist[i][i] = 0;
        for (int[] e : edges) { dist[e[0]][e[1]] = e[2]; dist[e[1]][e[0]] = e[2]; }

        for (int k = 0; k < n; k++)
            for (int i = 0; i < n; i++)
                for (int j = 0; j < n; j++)
                    dist[i][j] = Math.min(dist[i][j], dist[i][k] + dist[k][j]);

        int minCount = n, result = -1;
        for (int i = 0; i < n; i++) {
            int count = 0;
            for (int j = 0; j < n; j++) if (i != j && dist[i][j] <= distanceThreshold) count++;
            if (count <= minCount) { minCount = count; result = i; }
        }
        return result;
    }

    public static void main(String[] args) {
        Problem15_FindCityWithSmallestNeighbors solver = new Problem15_FindCityWithSmallestNeighbors();
        System.out.println(solver.findTheCity(4, new int[][]{{0,1,3},{1,2,1},{1,3,4},{2,3,1}}, 4)); // 3
    }
}
