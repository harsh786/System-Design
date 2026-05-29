import java.util.*;

/**
 * Problem 37: Percolation
 * 
 * Classic problem: n x n grid, initially all blocked. Open sites one by one.
 * System percolates when top row connects to bottom row.
 * 
 * Approach: Union-Find with virtual top and bottom nodes.
 * When opening a site, union with adjacent open sites. Check if virtual top
 * connects to virtual bottom.
 * 
 * Time: O(n² * α(n²)) for full grid, Space: O(n²)
 * 
 * Production Analogy: Network percolation theory - at what point does a network
 * become fully connected from entry points to exit points?
 */
public class Problem37_Percolation {
    
    int[] parent, rank;
    boolean[][] open;
    int n;
    int top, bottom;
    
    public Problem37_Percolation(int n) {
        this.n = n;
        parent = new int[n * n + 2]; rank = new int[n * n + 2];
        for (int i = 0; i < parent.length; i++) parent[i] = i;
        open = new boolean[n][n];
        top = n * n;
        bottom = n * n + 1;
    }
    
    public void openSite(int row, int col) {
        if (open[row][col]) return;
        open[row][col] = true;
        int id = row * n + col;
        
        if (row == 0) union(id, top);
        if (row == n - 1) union(id, bottom);
        
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        for (int[] d : dirs) {
            int nr = row + d[0], nc = col + d[1];
            if (nr >= 0 && nr < n && nc >= 0 && nc < n && open[nr][nc]) {
                union(id, nr * n + nc);
            }
        }
    }
    
    public boolean percolates() {
        return find(top) == find(bottom);
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
        Problem37_Percolation perc = new Problem37_Percolation(3);
        perc.openSite(0, 1);
        System.out.println(perc.percolates()); // false
        perc.openSite(1, 1);
        System.out.println(perc.percolates()); // false
        perc.openSite(2, 1);
        System.out.println(perc.percolates()); // true
        
        // Test 2: no path
        Problem37_Percolation perc2 = new Problem37_Percolation(3);
        perc2.openSite(0, 0);
        perc2.openSite(2, 2);
        System.out.println(perc2.percolates()); // false
    }
}
