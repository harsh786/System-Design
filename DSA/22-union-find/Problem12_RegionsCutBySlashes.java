import java.util.*;

/**
 * Problem 12: Regions Cut By Slashes (LeetCode 959)
 * 
 * An n x n grid with '/', '\', ' ' characters. Count regions formed.
 * 
 * Approach: Each cell is divided into 4 triangles (top=0, right=1, bottom=2, left=3).
 * Union triangles within a cell based on the character, and union adjacent triangles
 * between neighboring cells. Count remaining components.
 * 
 * Time: O(n² * α(n²)), Space: O(n²)
 * 
 * Production Analogy: Network segmentation with firewalls (slashes) dividing
 * a flat network into isolated zones.
 */
public class Problem12_RegionsCutBySlashes {
    
    int[] parent, rank;
    int components;
    
    public int regionsBySlashes(String[] grid) {
        int n = grid.length;
        parent = new int[n * n * 4];
        rank = new int[n * n * 4];
        components = n * n * 4;
        for (int i = 0; i < parent.length; i++) parent[i] = i;
        
        for (int i = 0; i < n; i++) {
            for (int j = 0; j < n; j++) {
                int base = (i * n + j) * 4;
                char c = grid[i].charAt(j);
                
                // Internal unions within cell
                if (c == '/') {
                    union(base + 0, base + 3); // top-left
                    union(base + 1, base + 2); // right-bottom
                } else if (c == '\\') {
                    union(base + 0, base + 1); // top-right
                    union(base + 2, base + 3); // bottom-left
                } else {
                    union(base + 0, base + 1);
                    union(base + 1, base + 2);
                    union(base + 2, base + 3);
                }
                
                // Union with neighbors
                if (i + 1 < n) union(base + 2, ((i+1)*n+j)*4 + 0); // bottom-top
                if (j + 1 < n) union(base + 1, (i*n+j+1)*4 + 3);   // right-left
            }
        }
        return components;
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
        components--;
    }
    
    public static void main(String[] args) {
        Problem12_RegionsCutBySlashes sol = new Problem12_RegionsCutBySlashes();
        System.out.println(sol.regionsBySlashes(new String[]{" /","/ "})); // 2
        
        sol = new Problem12_RegionsCutBySlashes();
        System.out.println(sol.regionsBySlashes(new String[]{" /","  "})); // 1
        
        sol = new Problem12_RegionsCutBySlashes();
        System.out.println(sol.regionsBySlashes(new String[]{"/\\","\\/"})); // 5
    }
}
