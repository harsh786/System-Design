import java.util.*;

/**
 * Problem 49: Floyd-Warshall All Pairs Shortest Path
 * 
 * Approach: DP. dist[i][j] = min(dist[i][j], dist[i][k] + dist[k][j]) for all intermediate k.
 * Time: O(V^3), Space: O(V^2)
 * 
 * Production Analogy: Precomputing all-pairs latency table for a service mesh to optimize routing decisions.
 */
public class Problem49_FloydWarshall {
    
    static final int INF = 100000000;
    
    public int[][] floydWarshall(int n, int[][] edges) {
        int[][] dist = new int[n][n];
        for (int[] row : dist) Arrays.fill(row, INF);
        for (int i = 0; i < n; i++) dist[i][i] = 0;
        for (int[] e : edges) dist[e[0]][e[1]] = e[2];
        
        for (int k = 0; k < n; k++)
            for (int i = 0; i < n; i++)
                for (int j = 0; j < n; j++)
                    if (dist[i][k] + dist[k][j] < dist[i][j])
                        dist[i][j] = dist[i][k] + dist[k][j];
        return dist;
    }
    
    public static void main(String[] args) {
        Problem49_FloydWarshall sol = new Problem49_FloydWarshall();
        int[][] edges = {{0,1,3},{0,3,7},{1,0,8},{1,2,2},{2,0,5},{2,3,1},{3,0,2}};
        int[][] dist = sol.floydWarshall(4, edges);
        for (int[] row : dist) System.out.println(Arrays.toString(row));
        // Expected: [0,3,5,6], [5,0,2,3], [3,6,0,1], [2,5,7,0]
    }
}
