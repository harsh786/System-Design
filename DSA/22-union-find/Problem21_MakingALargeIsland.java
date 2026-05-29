import java.util.*;

/**
 * Problem 21: Making A Large Island (LeetCode 827)
 * 
 * Given binary grid, change at most one 0 to 1, find largest island.
 * 
 * Approach: Use Union-Find to find all islands and their sizes.
 * For each 0 cell, check unique neighboring island components and sum their sizes + 1.
 * 
 * Time: O(n²), Space: O(n²)
 * 
 * Production Analogy: Capacity planning - if we add one more link between clusters,
 * what's the maximum reachable cluster size?
 */
public class Problem21_MakingALargeIsland {
    
    int[] parent, rank, size;
    
    public int largestIsland(int[][] grid) {
        int n = grid.length;
        parent = new int[n * n]; rank = new int[n * n]; size = new int[n * n];
        for (int i = 0; i < n * n; i++) { parent[i] = i; size[i] = 1; }
        
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        
        for (int i = 0; i < n; i++)
            for (int j = 0; j < n; j++)
                if (grid[i][j] == 1) {
                    if (i+1 < n && grid[i+1][j] == 1) union(i*n+j, (i+1)*n+j);
                    if (j+1 < n && grid[i][j+1] == 1) union(i*n+j, i*n+j+1);
                }
        
        int max = 0;
        // Check existing island sizes
        for (int i = 0; i < n * n; i++) if (grid[i/n][i%n] == 1) max = Math.max(max, size[find(i)]);
        
        // Try flipping each 0
        for (int i = 0; i < n; i++)
            for (int j = 0; j < n; j++) {
                if (grid[i][j] == 0) {
                    Set<Integer> seen = new HashSet<>();
                    int total = 1;
                    for (int[] d : dirs) {
                        int ni = i+d[0], nj = j+d[1];
                        if (ni >= 0 && ni < n && nj >= 0 && nj < n && grid[ni][nj] == 1) {
                            int root = find(ni*n+nj);
                            if (seen.add(root)) total += size[root];
                        }
                    }
                    max = Math.max(max, total);
                }
            }
        return max;
    }
    
    private int find(int x) {
        if (parent[x] != x) parent[x] = find(parent[x]);
        return parent[x];
    }
    
    private void union(int x, int y) {
        int px = find(x), py = find(y);
        if (px == py) return;
        if (rank[px] < rank[py]) { parent[px] = py; size[py] += size[px]; }
        else if (rank[px] > rank[py]) { parent[py] = px; size[px] += size[py]; }
        else { parent[py] = px; size[px] += size[py]; rank[px]++; }
    }
    
    public static void main(String[] args) {
        Problem21_MakingALargeIsland sol = new Problem21_MakingALargeIsland();
        System.out.println(sol.largestIsland(new int[][]{{1,0},{0,1}})); // 3
        System.out.println(sol.largestIsland(new int[][]{{1,1},{1,0}})); // 4
        System.out.println(sol.largestIsland(new int[][]{{1,1},{1,1}})); // 4
    }
}
