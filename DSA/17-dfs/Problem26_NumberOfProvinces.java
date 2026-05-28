/**
 * Problem: Number of Provinces (LeetCode 547)
 * Approach: DFS on adjacency matrix to count connected components
 * Time: O(N^2), Space: O(N)
 * Production Analogy: Identifying isolated network segments in a data center
 */
public class Problem26_NumberOfProvinces {
    public int findCircleNum(int[][] isConnected) {
        int n = isConnected.length, count = 0;
        boolean[] visited = new boolean[n];
        for (int i = 0; i < n; i++) {
            if (!visited[i]) { dfs(isConnected, i, visited); count++; }
        }
        return count;
    }

    private void dfs(int[][] g, int i, boolean[] visited) {
        visited[i] = true;
        for (int j = 0; j < g.length; j++)
            if (g[i][j] == 1 && !visited[j]) dfs(g, j, visited);
    }

    public static void main(String[] args) {
        int[][] m = {{1,1,0},{1,1,0},{0,0,1}};
        System.out.println(new Problem26_NumberOfProvinces().findCircleNum(m)); // 2
    }
}
