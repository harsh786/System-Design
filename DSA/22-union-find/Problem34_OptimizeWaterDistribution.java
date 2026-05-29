import java.util.*;

/**
 * Problem 34: Optimize Water Distribution in a Village (LeetCode 1168)
 * 
 * n houses. wells[i] = cost to build well at house i.
 * pipes[j] = [house1, house2, cost] to connect two houses.
 * Find minimum cost to supply water to all houses.
 * 
 * Approach: Add virtual node 0. Edge from 0 to house i = wells[i] (building a well).
 * Now it's just MST with Kruskal's.
 * 
 * Time: O((n+p)*log(n+p)), Space: O(n+p)
 * 
 * Production Analogy: CDN origin selection - each edge server can either pull from
 * origin (well cost) or from another edge server (pipe cost). Minimize total cost.
 */
public class Problem34_OptimizeWaterDistribution {
    
    int[] parent, rank;
    
    public int minCostToSupplyWater(int n, int[] wells, int[][] pipes) {
        List<int[]> edges = new ArrayList<>();
        for (int i = 0; i < n; i++) edges.add(new int[]{0, i + 1, wells[i]});
        for (int[] p : pipes) edges.add(p);
        edges.sort((a, b) -> a[2] - b[2]);
        
        parent = new int[n + 1]; rank = new int[n + 1];
        for (int i = 0; i <= n; i++) parent[i] = i;
        
        int cost = 0;
        for (int[] e : edges) {
            if (union(e[0], e[1])) cost += e[2];
        }
        return cost;
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
        Problem34_OptimizeWaterDistribution sol = new Problem34_OptimizeWaterDistribution();
        System.out.println(sol.minCostToSupplyWater(3, new int[]{1,2,2}, new int[][]{{1,2,1},{2,3,1}})); // 3
        System.out.println(sol.minCostToSupplyWater(2, new int[]{1,1}, new int[][]{{1,2,1}})); // 2
    }
}
