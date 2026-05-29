import java.util.*;

/**
 * Problem 3: Redundant Connection
 * 
 * Given an undirected graph that started as a tree with one additional edge,
 * find the edge that can be removed to make it a tree again.
 * If multiple answers, return the one that occurs last in the input.
 * 
 * Approach: Process edges one by one. The first edge that connects two
 * already-connected nodes creates the cycle - that's our answer.
 * 
 * Time: O(n * α(n)), Space: O(n)
 * 
 * Production Analogy: Detecting redundant network links in a tree topology.
 * In spanning tree protocol (STP), switches identify and block redundant links
 * to prevent loops - this is exactly what we're doing.
 */
public class Problem03_RedundantConnection {
    
    int[] parent, rank;
    
    public int[] findRedundantConnection(int[][] edges) {
        int n = edges.length;
        parent = new int[n + 1];
        rank = new int[n + 1];
        for (int i = 0; i <= n; i++) parent[i] = i;
        
        for (int[] e : edges) {
            if (!union(e[0], e[1])) return e;
        }
        return new int[0];
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
        Problem03_RedundantConnection sol = new Problem03_RedundantConnection();
        
        // Test 1
        int[] res = sol.findRedundantConnection(new int[][]{{1,2},{1,3},{2,3}});
        System.out.println(Arrays.toString(res)); // [2,3]
        
        // Test 2
        res = sol.findRedundantConnection(new int[][]{{1,2},{2,3},{3,4},{1,4},{1,5}});
        System.out.println(Arrays.toString(res)); // [1,4]
    }
}
