import java.util.*;

/**
 * Problem 16: Bricks Falling When Hit (LeetCode 803)
 * 
 * Grid of bricks. Bricks connected to top row are stable. Hit bricks one at a time.
 * Return how many bricks fall after each hit.
 * 
 * Approach: Reverse time - start with all hits applied, add bricks back.
 * Use Union-Find with a virtual "roof" node. When adding back a brick,
 * the increase in roof-connected component size = bricks that fall.
 * 
 * Time: O(H * m*n * α(m*n)), Space: O(m*n)
 * 
 * Production Analogy: Cascading failure analysis in reverse - understanding
 * how many services recover when you restore a dependency.
 */
public class Problem16_BricksFallingWhenHit {
    
    int[] parent, rank, size;
    
    public int[] hitBricks(int[][] grid, int[][] hits) {
        int m = grid.length, n = grid[0].length;
        int[][] gridCopy = new int[m][n];
        for (int i = 0; i < m; i++) gridCopy[i] = grid[i].clone();
        
        // Remove all hit bricks
        for (int[] h : hits) gridCopy[h[0]][h[1]] = 0;
        
        // Initialize UF with virtual roof node = m*n
        int roof = m * n;
        parent = new int[m * n + 1]; rank = new int[m * n + 1]; size = new int[m * n + 1];
        for (int i = 0; i <= m * n; i++) { parent[i] = i; size[i] = 1; }
        
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        
        // Build UF for remaining bricks
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++) {
                if (gridCopy[i][j] == 1) {
                    if (i == 0) union(j, roof);
                    if (i > 0 && gridCopy[i-1][j] == 1) union(i*n+j, (i-1)*n+j);
                    if (j > 0 && gridCopy[i][j-1] == 1) union(i*n+j, i*n+j-1);
                }
            }
        
        // Process hits in reverse
        int[] result = new int[hits.length];
        for (int k = hits.length - 1; k >= 0; k--) {
            int r = hits[k][0], c = hits[k][1];
            if (grid[r][c] == 0) { result[k] = 0; continue; }
            
            int prevRoofSize = size[find(roof)];
            gridCopy[r][c] = 1;
            if (r == 0) union(r*n+c, roof);
            for (int[] d : dirs) {
                int nr = r+d[0], nc = c+d[1];
                if (nr >= 0 && nr < m && nc >= 0 && nc < n && gridCopy[nr][nc] == 1)
                    union(r*n+c, nr*n+nc);
            }
            int newRoofSize = size[find(roof)];
            result[k] = Math.max(0, newRoofSize - prevRoofSize - 1);
        }
        return result;
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
        Problem16_BricksFallingWhenHit sol = new Problem16_BricksFallingWhenHit();
        System.out.println(Arrays.toString(sol.hitBricks(
            new int[][]{{1,0,0,0},{1,1,1,0}}, new int[][]{{1,0}}))); // [2]
        
        sol = new Problem16_BricksFallingWhenHit();
        System.out.println(Arrays.toString(sol.hitBricks(
            new int[][]{{1,0,0,0},{1,1,0,0}}, new int[][]{{1,1},{1,0}}))); // [0,0]
    }
}
