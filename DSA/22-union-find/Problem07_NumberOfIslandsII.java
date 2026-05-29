import java.util.*;

/**
 * Problem 7: Number of Islands II (LeetCode 305)
 * 
 * Given m x n grid initially all water. Positions are added one by one as land.
 * After each addition, return the number of islands.
 * 
 * Approach: For each new land cell, start as new island (count++). Then check
 * 4 neighbors - if neighbor is land and different component, union them (count--).
 * 
 * Time: O(k * α(m*n)) where k = number of operations, Space: O(m*n)
 * 
 * Production Analogy: Dynamic cluster formation - as new servers come online,
 * they join existing clusters or form new ones. Real-time monitoring of cluster count.
 */
public class Problem07_NumberOfIslandsII {
    
    int[] parent, rank;
    int count;
    
    public List<Integer> numIslands2(int m, int n, int[][] positions) {
        parent = new int[m * n];
        rank = new int[m * n];
        Arrays.fill(parent, -1);
        count = 0;
        List<Integer> result = new ArrayList<>();
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        
        for (int[] pos : positions) {
            int r = pos[0], c = pos[1];
            int id = r * n + c;
            if (parent[id] != -1) { result.add(count); continue; } // already land
            parent[id] = id;
            count++;
            
            for (int[] d : dirs) {
                int nr = r + d[0], nc = c + d[1];
                int nid = nr * n + nc;
                if (nr >= 0 && nr < m && nc >= 0 && nc < n && parent[nid] != -1) {
                    union(id, nid);
                }
            }
            result.add(count);
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
        if (rank[px] < rank[py]) parent[px] = py;
        else if (rank[px] > rank[py]) parent[py] = px;
        else { parent[py] = px; rank[px]++; }
        count--;
    }
    
    public static void main(String[] args) {
        Problem07_NumberOfIslandsII sol = new Problem07_NumberOfIslandsII();
        
        List<Integer> res = sol.numIslands2(3, 3, new int[][]{{0,0},{0,1},{1,2},{2,1}});
        System.out.println(res); // [1, 1, 2, 3]
        
        // Test with duplicate position
        res = sol.numIslands2(2, 2, new int[][]{{0,0},{0,0},{1,1},{0,1}});
        System.out.println(res); // [1, 1, 2, 1]
    }
}
