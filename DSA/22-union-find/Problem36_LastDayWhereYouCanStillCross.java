import java.util.*;

/**
 * Problem 36: Last Day Where You Can Still Cross (LeetCode 1970)
 * 
 * Grid with cells flooding day by day. Find last day you can walk from top to bottom.
 * 
 * Approach: Reverse - start with all cells flooded, un-flood in reverse order.
 * Use Union-Find with virtual top/bottom nodes. First day top connects to bottom (in reverse) is answer.
 * 
 * Time: O(m*n * α(m*n)), Space: O(m*n)
 * 
 * Production Analogy: Infrastructure degradation - find the latest time at which
 * end-to-end connectivity still holds as links fail one by one.
 */
public class Problem36_LastDayWhereYouCanStillCross {
    
    int[] parent, rank;
    
    public int latestDayToCross(int row, int col, int[][] cells) {
        int n = row * col;
        parent = new int[n + 2]; rank = new int[n + 2]; // +2 for virtual top/bottom
        for (int i = 0; i < n + 2; i++) parent[i] = i;
        int top = n, bottom = n + 1;
        
        boolean[][] grid = new boolean[row][col];
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        
        // Process in reverse
        for (int day = cells.length - 1; day >= 0; day--) {
            int r = cells[day][0] - 1, c = cells[day][1] - 1;
            grid[r][c] = true;
            int id = r * col + c;
            
            if (r == 0) union(id, top);
            if (r == row - 1) union(id, bottom);
            
            for (int[] d : dirs) {
                int nr = r + d[0], nc = c + d[1];
                if (nr >= 0 && nr < row && nc >= 0 && nc < col && grid[nr][nc]) {
                    union(id, nr * col + nc);
                }
            }
            
            if (find(top) == find(bottom)) return day;
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
        Problem36_LastDayWhereYouCanStillCross sol = new Problem36_LastDayWhereYouCanStillCross();
        System.out.println(sol.latestDayToCross(2, 2, new int[][]{{1,1},{2,1},{1,2},{2,2}})); // 2
        System.out.println(sol.latestDayToCross(3, 3, new int[][]{{1,2},{2,1},{3,3},{2,2},{1,1},{1,3},{2,3},{3,2},{3,1}})); // 3
    }
}
