import java.util.*;

/**
 * Problem 2: Graph Valid Tree
 * 
 * Given n nodes and edges, determine if they form a valid tree.
 * A valid tree: connected (1 component) and no cycles (edges == n-1).
 * 
 * Union-Find detects cycles: if two nodes already share the same root
 * and we try to union them, a cycle exists.
 * 
 * Time: O(n + E * α(n)), Space: O(n)
 * 
 * Production Analogy: Validating a spanning tree topology in a network -
 * ensuring no redundant links that could cause broadcast storms (cycles)
 * while maintaining full connectivity.
 */
public class Problem02_GraphValidTree {
    
    int[] parent, rank;
    
    public boolean validTree(int n, int[][] edges) {
        if (edges.length != n - 1) return false; // Tree must have exactly n-1 edges
        
        parent = new int[n];
        rank = new int[n];
        for (int i = 0; i < n; i++) parent[i] = i;
        
        for (int[] e : edges) {
            if (!union(e[0], e[1])) return false; // Cycle detected
        }
        return true;
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
        Problem02_GraphValidTree sol = new Problem02_GraphValidTree();
        
        // Test 1: Valid tree
        System.out.println(sol.validTree(5, new int[][]{{0,1},{0,2},{0,3},{1,4}})); // true
        
        // Test 2: Has cycle
        System.out.println(sol.validTree(5, new int[][]{{0,1},{1,2},{2,3},{1,3},{1,4}})); // false
        
        // Test 3: Not connected (too few edges)
        System.out.println(sol.validTree(5, new int[][]{{0,1},{2,3}})); // false
        
        // Test 4: Single node
        System.out.println(sol.validTree(1, new int[][]{})); // true
    }
}
