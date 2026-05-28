import java.util.*;

/**
 * Problem 9: Redundant Connection (LeetCode 684)
 * 
 * Approach: Union-Find. The edge that creates a cycle is redundant.
 * Time: O(N * α(N)) ≈ O(N), Space: O(N)
 * 
 * Production Analogy: Detecting redundant network links that create loops in a spanning tree topology.
 */
public class Problem09_RedundantConnection {
    
    int[] parent, rank;
    
    public int[] findRedundantConnection(int[][] edges) {
        int n = edges.length;
        parent = new int[n + 1]; rank = new int[n + 1];
        for (int i = 1; i <= n; i++) parent[i] = i;
        for (int[] e : edges)
            if (!union(e[0], e[1])) return e;
        return new int[0];
    }
    
    int find(int x) { return parent[x] == x ? x : (parent[x] = find(parent[x])); }
    boolean union(int a, int b) {
        int pa = find(a), pb = find(b);
        if (pa == pb) return false;
        if (rank[pa] < rank[pb]) parent[pa] = pb;
        else if (rank[pa] > rank[pb]) parent[pb] = pa;
        else { parent[pb] = pa; rank[pa]++; }
        return true;
    }
    
    public static void main(String[] args) {
        Problem09_RedundantConnection sol = new Problem09_RedundantConnection();
        System.out.println(Arrays.toString(sol.findRedundantConnection(new int[][]{{1,2},{1,3},{2,3}}))); // [2,3]
        sol = new Problem09_RedundantConnection();
        System.out.println(Arrays.toString(sol.findRedundantConnection(new int[][]{{1,2},{2,3},{3,4},{1,4},{1,5}}))); // [1,4]
    }
}
