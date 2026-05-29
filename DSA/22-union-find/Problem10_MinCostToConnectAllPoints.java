import java.util.*;

/**
 * Problem 10: Min Cost to Connect All Points (LeetCode 1584)
 * 
 * Given points on 2D plane, find minimum cost to connect all points where
 * cost = Manhattan distance. This is Minimum Spanning Tree (Kruskal's).
 * 
 * Approach: Generate all edges with Manhattan distances, sort by cost,
 * greedily add edges using Union-Find to avoid cycles (Kruskal's algorithm).
 * 
 * Time: O(n² log n) for sorting edges, Space: O(n²)
 * 
 * Production Analogy: Minimum cost network topology - connecting data centers
 * with the cheapest possible fiber optic links while ensuring full connectivity.
 */
public class Problem10_MinCostToConnectAllPoints {
    
    int[] parent, rank;
    
    public int minCostConnectPoints(int[][] points) {
        int n = points.length;
        List<int[]> edges = new ArrayList<>(); // [cost, i, j]
        
        for (int i = 0; i < n; i++)
            for (int j = i + 1; j < n; j++) {
                int cost = Math.abs(points[i][0] - points[j][0]) + Math.abs(points[i][1] - points[j][1]);
                edges.add(new int[]{cost, i, j});
            }
        
        edges.sort((a, b) -> a[0] - b[0]);
        
        parent = new int[n]; rank = new int[n];
        for (int i = 0; i < n; i++) parent[i] = i;
        
        int totalCost = 0, edgesUsed = 0;
        for (int[] e : edges) {
            if (union(e[1], e[2])) {
                totalCost += e[0];
                if (++edgesUsed == n - 1) break;
            }
        }
        return totalCost;
    }
    
    private int find(int x) {
        if (parent[x] != x) parent[x] = find(parent[x]);
        return parent[x];
    }
    
    private boolean union(int x, int y) {
        int px = find(x), py = find(y);
        if (px == py) return false;
        if (rank[px] < rank[py]) parent[px] = py;
        else if (rank[px] > rank[py]) parent[py] = px;
        else { parent[py] = px; rank[px]++; }
        return true;
    }
    
    public static void main(String[] args) {
        Problem10_MinCostToConnectAllPoints sol = new Problem10_MinCostToConnectAllPoints();
        
        System.out.println(sol.minCostConnectPoints(new int[][]{{0,0},{2,2},{3,10},{5,2},{7,0}})); // 20
        System.out.println(sol.minCostConnectPoints(new int[][]{{3,12},{-2,5},{-4,1}})); // 18
    }
}
