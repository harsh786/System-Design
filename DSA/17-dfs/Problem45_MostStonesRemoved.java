import java.util.*;

/**
 * Problem: Most Stones Removed with Same Row or Column (LeetCode 947)
 * Approach: DFS/Union-Find - stones in same row/col form connected component; answer = total - components
 * Time: O(N^2), Space: O(N)
 * Production Analogy: Maximizing resource consolidation across shared dimensions
 */
public class Problem45_MostStonesRemoved {
    public int removeStones(int[][] stones) {
        int n = stones.length;
        boolean[] visited = new boolean[n];
        int components = 0;
        for (int i = 0; i < n; i++) {
            if (!visited[i]) { dfs(stones, i, visited); components++; }
        }
        return n - components;
    }

    private void dfs(int[][] stones, int idx, boolean[] visited) {
        visited[idx] = true;
        for (int i = 0; i < stones.length; i++) {
            if (!visited[i] && (stones[i][0] == stones[idx][0] || stones[i][1] == stones[idx][1]))
                dfs(stones, i, visited);
        }
    }

    public static void main(String[] args) {
        int[][] stones = {{0,0},{0,1},{1,0},{1,2},{2,1},{2,2}};
        System.out.println(new Problem45_MostStonesRemoved().removeStones(stones)); // 5
    }
}
