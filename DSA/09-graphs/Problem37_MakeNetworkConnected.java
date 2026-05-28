import java.util.*;

/**
 * Problem 37: Number of Operations to Make Network Connected (LeetCode 1319)
 * 
 * Approach: Need at least n-1 edges. Count components with Union-Find. Answer = components - 1.
 * Time: O(E * α(N)), Space: O(N)
 * 
 * Production Analogy: Minimum cable moves needed to connect all isolated server racks.
 */
public class Problem37_MakeNetworkConnected {
    
    int[] parent, rank;
    int find(int x) { return parent[x] == x ? x : (parent[x] = find(parent[x])); }
    
    public int makeConnected(int n, int[][] connections) {
        if (connections.length < n - 1) return -1;
        parent = new int[n]; rank = new int[n];
        for (int i = 0; i < n; i++) parent[i] = i;
        int components = n;
        for (int[] c : connections) {
            int pa = find(c[0]), pb = find(c[1]);
            if (pa != pb) { parent[pa] = pb; components--; }
        }
        return components - 1;
    }
    
    public static void main(String[] args) {
        Problem37_MakeNetworkConnected sol = new Problem37_MakeNetworkConnected();
        System.out.println(sol.makeConnected(4, new int[][]{{0,1},{0,2},{1,2}})); // 1
        System.out.println(sol.makeConnected(6, new int[][]{{0,1},{0,2},{0,3},{1,2},{1,3}})); // 2
        System.out.println(sol.makeConnected(6, new int[][]{{0,1},{0,2},{0,3},{1,2}})); // -1
    }
}
