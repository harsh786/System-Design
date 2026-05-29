import java.util.*;

/**
 * Problem 6: Number of Islands (Union-Find approach)
 * 
 * Given a 2D grid of '1's (land) and '0's (water), count the number of islands.
 * 
 * Union-Find approach: Treat each land cell as a node. Union adjacent land cells.
 * Count distinct components among land cells.
 * 
 * Time: O(m*n * α(m*n)), Space: O(m*n)
 * 
 * Production Analogy: In a distributed cache cluster, identifying groups of
 * co-located cache nodes that can communicate directly (same rack/availability zone).
 */
public class Problem06_NumberOfIslands {
    
    int[] parent, rank;
    int count;
    
    public int numIslands(char[][] grid) {
        int m = grid.length, n = grid[0].length;
        parent = new int[m * n];
        rank = new int[m * n];
        count = 0;
        
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++) {
                if (grid[i][j] == '1') {
                    parent[i * n + j] = i * n + j;
                    count++;
                }
            }
        
        int[][] dirs = {{0,1},{1,0}};
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++) {
                if (grid[i][j] == '1') {
                    for (int[] d : dirs) {
                        int ni = i + d[0], nj = j + d[1];
                        if (ni < m && nj < n && grid[ni][nj] == '1') {
                            union(i * n + j, ni * n + nj);
                        }
                    }
                }
            }
        return count;
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
        count--;
    }
    
    public static void main(String[] args) {
        Problem06_NumberOfIslands sol = new Problem06_NumberOfIslands();
        
        char[][] grid1 = {
            {'1','1','1','1','0'},
            {'1','1','0','1','0'},
            {'1','1','0','0','0'},
            {'0','0','0','0','0'}
        };
        System.out.println(sol.numIslands(grid1)); // 1
        
        char[][] grid2 = {
            {'1','1','0','0','0'},
            {'1','1','0','0','0'},
            {'0','0','1','0','0'},
            {'0','0','0','1','1'}
        };
        System.out.println(sol.numIslands(grid2)); // 3
    }
}
