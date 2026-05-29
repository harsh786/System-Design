import java.util.*;

/**
 * Problem 1: Number of Connected Components in an Undirected Graph
 * 
 * Given n nodes labeled from 0 to n-1 and a list of undirected edges,
 * find the number of connected components.
 * 
 * Union-Find Approach:
 * - Path Compression: When finding root, make every node point directly to root.
 *   This flattens the tree, making subsequent finds O(α(n)) ≈ O(1).
 * - Union by Rank: Always attach smaller tree under root of larger tree.
 *   This keeps tree height minimal.
 * 
 * Time Complexity: O(n + E * α(n)) where E = edges, α = inverse Ackermann
 * Space Complexity: O(n)
 * 
 * Production Analogy: Network partition detection - determining how many isolated
 * clusters exist in a distributed system. Each server is a node, each network link
 * is an edge. The number of components tells you how many partitions exist.
 */
public class Problem01_NumberOfConnectedComponents {
    
    int[] parent;
    int[] rank;
    int components;
    
    public int countComponents(int n, int[][] edges) {
        parent = new int[n];
        rank = new int[n];
        components = n;
        
        for (int i = 0; i < n; i++) parent[i] = i;
        
        for (int[] edge : edges) {
            union(edge[0], edge[1]);
        }
        return components;
    }
    
    private int find(int x) {
        if (parent[x] != x) {
            parent[x] = find(parent[x]); // Path compression
        }
        return parent[x];
    }
    
    private void union(int x, int y) {
        int px = find(x), py = find(y);
        if (px == py) return;
        // Union by rank
        if (rank[px] < rank[py]) { parent[px] = py; }
        else if (rank[px] > rank[py]) { parent[py] = px; }
        else { parent[py] = px; rank[px]++; }
        components--;
    }
    
    public static void main(String[] args) {
        Problem01_NumberOfConnectedComponents sol = new Problem01_NumberOfConnectedComponents();
        
        // Test 1: Two components
        System.out.println(sol.countComponents(5, new int[][]{{0,1},{1,2},{3,4}})); // 2
        
        // Test 2: All connected
        System.out.println(sol.countComponents(5, new int[][]{{0,1},{1,2},{2,3},{3,4}})); // 1
        
        // Test 3: No edges - each node is its own component
        System.out.println(sol.countComponents(5, new int[][]{})); // 5
        
        // Test 4: Single node
        System.out.println(sol.countComponents(1, new int[][]{})); // 1
    }
}
