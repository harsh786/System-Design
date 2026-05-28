import java.util.*;

/**
 * Problem 21: Graph Valid Tree (LeetCode 261)
 * 
 * Approach: A valid tree has n-1 edges and is fully connected. Use Union-Find.
 * Time: O(V + E), Space: O(V)
 * 
 * Production Analogy: Verifying a network topology forms a spanning tree (no loops, fully connected).
 */
public class Problem21_GraphValidTree {
    
    public boolean validTree(int n, int[][] edges) {
        if (edges.length != n - 1) return false;
        int[] parent = new int[n];
        for (int i = 0; i < n; i++) parent[i] = i;
        for (int[] e : edges) {
            int p1 = find(parent, e[0]), p2 = find(parent, e[1]);
            if (p1 == p2) return false;
            parent[p1] = p2;
        }
        return true;
    }
    
    int find(int[] p, int x) { return p[x] == x ? x : (p[x] = find(p, p[x])); }
    
    public static void main(String[] args) {
        Problem21_GraphValidTree sol = new Problem21_GraphValidTree();
        System.out.println(sol.validTree(5, new int[][]{{0,1},{0,2},{0,3},{1,4}})); // true
        System.out.println(sol.validTree(5, new int[][]{{0,1},{1,2},{2,3},{1,3},{1,4}})); // false
        System.out.println(sol.validTree(1, new int[][]{})); // true
    }
}
