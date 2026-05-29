import java.util.*;

/**
 * Problem 15: Swim in Rising Water (LeetCode 778) - Union-Find approach
 * 
 * At time t, water level is t. Find minimum time to swim from (0,0) to (n-1,n-1).
 * Can swim to adjacent cell if both cells have elevation <= t.
 * 
 * Approach: Sort cells by elevation. Process in order, union with neighbors
 * that have already been processed. Stop when (0,0) connects to (n-1,n-1).
 * 
 * Time: O(n² log n²), Space: O(n²)
 * 
 * Production Analogy: Progressive service recovery - services come online at
 * different times. Find earliest time when source can reach destination.
 */
public class Problem15_SwimInRisingWater {
    
    int[] parent, rank;
    
    public int swimInWater(int[][] grid) {
        int n = grid.length;
        int[][] cells = new int[n * n][2];
        for (int i = 0; i < n; i++)
            for (int j = 0; j < n; j++)
                cells[grid[i][j]] = new int[]{i, j};
        
        parent = new int[n * n]; rank = new int[n * n];
        for (int i = 0; i < n * n; i++) parent[i] = i;
        boolean[][] visited = new boolean[n][n];
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        
        for (int t = 0; t < n * n; t++) {
            int r = cells[t][0], c = cells[t][1];
            visited[r][c] = true;
            for (int[] d : dirs) {
                int nr = r + d[0], nc = c + d[1];
                if (nr >= 0 && nr < n && nc >= 0 && nc < n && visited[nr][nc]) {
                    union(r * n + c, nr * n + nc);
                }
            }
            if (find(0) == find(n * n - 1)) return t;
        }
        return n * n - 1;
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
        Problem15_SwimInRisingWater sol = new Problem15_SwimInRisingWater();
        System.out.println(sol.swimInWater(new int[][]{{0,2},{1,3}})); // 3
        System.out.println(sol.swimInWater(new int[][]{
            {0,1,2,3,4},{24,23,22,21,5},{12,13,14,15,16},{11,17,18,19,20},{10,9,8,7,6}})); // 16
    }
}
