import java.util.*;

/**
 * Problem 30: Regions Cut By Slashes (LeetCode 959)
 * 
 * Approach: Upscale grid 3x. '/' and '\\' become lines in 3x3 sub-grid. Count islands.
 * Time: O(N^2), Space: O(N^2)
 * 
 * Production Analogy: Partitioning a shared memory space with barriers into isolated regions.
 */
public class Problem30_RegionsCutBySlashes {
    
    public int regionsBySlashes(String[] grid) {
        int n = grid.length, size = n * 3;
        boolean[][] g = new boolean[size][size];
        for (int i = 0; i < n; i++)
            for (int j = 0; j < n; j++) {
                if (grid[i].charAt(j) == '/') { g[i*3][j*3+2]=true; g[i*3+1][j*3+1]=true; g[i*3+2][j*3]=true; }
                else if (grid[i].charAt(j) == '\\') { g[i*3][j*3]=true; g[i*3+1][j*3+1]=true; g[i*3+2][j*3+2]=true; }
            }
        int count = 0;
        for (int i = 0; i < size; i++)
            for (int j = 0; j < size; j++)
                if (!g[i][j]) { count++; fill(g, i, j, size); }
        return count;
    }
    
    void fill(boolean[][] g, int i, int j, int size) {
        if (i<0||i>=size||j<0||j>=size||g[i][j]) return;
        g[i][j] = true;
        fill(g,i+1,j,size); fill(g,i-1,j,size); fill(g,i,j+1,size); fill(g,i,j-1,size);
    }
    
    public static void main(String[] args) {
        Problem30_RegionsCutBySlashes sol = new Problem30_RegionsCutBySlashes();
        System.out.println(sol.regionsBySlashes(new String[]{" /","/ "})); // 2
        System.out.println(sol.regionsBySlashes(new String[]{" /","  "})); // 1
        System.out.println(sol.regionsBySlashes(new String[]{"/\\","\\/"})); // 4 (actually depends on escaping)
    }
}
