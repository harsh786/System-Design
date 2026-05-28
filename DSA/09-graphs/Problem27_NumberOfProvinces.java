import java.util.*;

/**
 * Problem 27: Number of Provinces (LeetCode 547)
 * 
 * Approach: Union-Find or DFS on adjacency matrix. Count connected components.
 * Time: O(N^2), Space: O(N)
 * 
 * Production Analogy: Counting isolated network segments in a peer-to-peer topology.
 */
public class Problem27_NumberOfProvinces {
    
    public int findCircleNum(int[][] isConnected) {
        int n = isConnected.length, count = 0;
        boolean[] visited = new boolean[n];
        for (int i = 0; i < n; i++) {
            if (!visited[i]) {
                count++;
                dfs(isConnected, visited, i, n);
            }
        }
        return count;
    }
    
    void dfs(int[][] g, boolean[] visited, int node, int n) {
        visited[node] = true;
        for (int j = 0; j < n; j++)
            if (g[node][j] == 1 && !visited[j]) dfs(g, visited, j, n);
    }
    
    public static void main(String[] args) {
        Problem27_NumberOfProvinces sol = new Problem27_NumberOfProvinces();
        System.out.println(sol.findCircleNum(new int[][]{{1,1,0},{1,1,0},{0,0,1}})); // 2
        System.out.println(sol.findCircleNum(new int[][]{{1,0,0},{0,1,0},{0,0,1}})); // 3
    }
}
