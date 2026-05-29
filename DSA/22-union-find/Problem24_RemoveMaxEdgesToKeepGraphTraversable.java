import java.util.*;

/**
 * Problem 24: Remove Max Number of Edges to Keep Graph Fully Traversable (LeetCode 1579)
 * 
 * Type 1: Alice only, Type 2: Bob only, Type 3: Both.
 * Remove max edges while keeping graph traversable for both.
 * 
 * Approach: Prioritize type 3 edges (shared). Use two separate UF structures.
 * First add type 3 edges, then type 1 for Alice and type 2 for Bob.
 * Count edges not needed (already connected).
 * 
 * Time: O(E * α(n)), Space: O(n)
 * 
 * Production Analogy: Multi-tenant network optimization - shared links serve both
 * tenants, dedicated links only one. Minimize total links while maintaining connectivity.
 */
public class Problem24_RemoveMaxEdgesToKeepGraphTraversable {
    
    int[] parentA, rankA, parentB, rankB;
    int compA, compB;
    
    public int maxNumEdgesToRemove(int n, int[][] edges) {
        parentA = new int[n+1]; rankA = new int[n+1];
        parentB = new int[n+1]; rankB = new int[n+1];
        for (int i = 0; i <= n; i++) { parentA[i] = i; parentB[i] = i; }
        compA = n; compB = n;
        int removed = 0;
        
        // Type 3 first
        for (int[] e : edges) {
            if (e[0] == 3) {
                boolean a = union(parentA, rankA, e[1], e[2], true);
                boolean b = union(parentB, rankB, e[1], e[2], false);
                if (!a && !b) removed++;
            }
        }
        // Type 1 and 2
        for (int[] e : edges) {
            if (e[0] == 1) { if (!union(parentA, rankA, e[1], e[2], true)) removed++; }
            else if (e[0] == 2) { if (!union(parentB, rankB, e[1], e[2], false)) removed++; }
        }
        
        if (compA != 1 || compB != 1) return -1;
        return removed;
    }
    
    private int find(int[] par, int x) {
        if (par[x] != x) par[x] = find(par, par[x]);
        return par[x];
    }
    
    private boolean union(int[] par, int[] rnk, int x, int y, boolean isA) {
        int px = find(par, x), py = find(par, y);
        if (px == py) return false;
        if (rnk[px] < rnk[py]) par[px] = py;
        else if (rnk[px] > rnk[py]) par[py] = px;
        else { par[py] = px; rnk[px]++; }
        if (isA) compA--; else compB--;
        return true;
    }
    
    public static void main(String[] args) {
        Problem24_RemoveMaxEdgesToKeepGraphTraversable sol = new Problem24_RemoveMaxEdgesToKeepGraphTraversable();
        System.out.println(sol.maxNumEdgesToRemove(4, new int[][]{
            {3,1,2},{3,2,3},{1,1,3},{1,2,4},{1,1,2},{2,3,4}})); // 2
    }
}
