import java.util.*;

/**
 * Problem 23: Find if Path Exists in Graph (LeetCode 1971)
 * 
 * Time: O(E * α(n)), Space: O(n)
 * 
 * Production Analogy: Basic reachability check - can service A communicate with service B?
 */
public class Problem23_FindIfPathExistsInGraph {
    
    int[] parent, rank;
    
    public boolean validPath(int n, int[][] edges, int source, int destination) {
        parent = new int[n]; rank = new int[n];
        for (int i = 0; i < n; i++) parent[i] = i;
        for (int[] e : edges) union(e[0], e[1]);
        return find(source) == find(destination);
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
        Problem23_FindIfPathExistsInGraph sol = new Problem23_FindIfPathExistsInGraph();
        System.out.println(sol.validPath(3, new int[][]{{0,1},{1,2},{2,0}}, 0, 2)); // true
        
        sol = new Problem23_FindIfPathExistsInGraph();
        System.out.println(sol.validPath(6, new int[][]{{0,1},{0,2},{3,5},{5,4},{4,3}}, 0, 5)); // false
    }
}
