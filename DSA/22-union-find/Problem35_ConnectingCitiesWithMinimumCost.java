import java.util.*;

/**
 * Problem 35: Connecting Cities With Minimum Cost (LeetCode 1135)
 * 
 * Standard MST problem. Connect all cities with minimum cost. Return -1 if impossible.
 * 
 * Time: O(E*logE + E*α(n)), Space: O(n)
 * 
 * Production Analogy: Minimum cost to interconnect all regional offices with VPN tunnels.
 */
public class Problem35_ConnectingCitiesWithMinimumCost {
    
    int[] parent, rank;
    
    public int minimumCost(int n, int[][] connections) {
        Arrays.sort(connections, (a, b) -> a[2] - b[2]);
        parent = new int[n + 1]; rank = new int[n + 1];
        for (int i = 0; i <= n; i++) parent[i] = i;
        
        int cost = 0, edges = 0;
        for (int[] c : connections) {
            if (union(c[0], c[1])) {
                cost += c[2];
                if (++edges == n - 1) return cost;
            }
        }
        return -1;
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
        Problem35_ConnectingCitiesWithMinimumCost sol = new Problem35_ConnectingCitiesWithMinimumCost();
        System.out.println(sol.minimumCost(3, new int[][]{{1,2,5},{1,3,6},{2,3,1}})); // 6
        System.out.println(sol.minimumCost(4, new int[][]{{1,2,3},{3,4,4}})); // -1
    }
}
