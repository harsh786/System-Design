import java.util.*;

/**
 * Problem 14: Path With Minimum Effort (LeetCode 1631) - Union-Find approach
 * 
 * Find path from top-left to bottom-right minimizing the maximum absolute difference
 * between consecutive cells. Union-Find approach: sort all edges by weight,
 * add them one by one until top-left and bottom-right are connected.
 * 
 * Time: O(m*n*log(m*n)), Space: O(m*n)
 * 
 * Production Analogy: Finding the network path with minimum bottleneck bandwidth -
 * ensuring the weakest link in the chain is as strong as possible.
 */
public class Problem14_PathWithMinimumEffort {
    
    int[] parent, rank;
    
    public int minimumEffortPath(int[][] heights) {
        int m = heights.length, n = heights[0].length;
        List<int[]> edges = new ArrayList<>(); // [effort, cell1, cell2]
        
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++) {
                if (i + 1 < m) edges.add(new int[]{Math.abs(heights[i][j] - heights[i+1][j]), i*n+j, (i+1)*n+j});
                if (j + 1 < n) edges.add(new int[]{Math.abs(heights[i][j] - heights[i][j+1]), i*n+j, i*n+j+1});
            }
        
        edges.sort((a, b) -> a[0] - b[0]);
        parent = new int[m * n]; rank = new int[m * n];
        for (int i = 0; i < m * n; i++) parent[i] = i;
        
        for (int[] e : edges) {
            union(e[1], e[2]);
            if (find(0) == find(m * n - 1)) return e[0];
        }
        return 0;
    }
    
    private int find(int x) {
        if (parent[x] != x) parent[x] = find(parent[x]);
        return parent[x];
    }
    
    private void union(int x, int y) {
        int px = find(x), py = find(y);
        if (px == py) return;
        if (rank[px] < rank[py]) parent[px] = py;
        else if (rank[px] > rank[py]) parent[py] = px;
        else { parent[py] = px; rank[px]++; }
    }
    
    public static void main(String[] args) {
        Problem14_PathWithMinimumEffort sol = new Problem14_PathWithMinimumEffort();
        System.out.println(sol.minimumEffortPath(new int[][]{{1,2,2},{3,8,2},{5,3,5}})); // 2
        System.out.println(sol.minimumEffortPath(new int[][]{{1,2,3},{3,8,4},{5,3,5}})); // 1
        System.out.println(sol.minimumEffortPath(new int[][]{{1,2,1,1,1},{1,2,1,2,1},{1,2,1,2,1},{1,2,1,2,1},{1,1,1,2,1}})); // 0
    }
}
