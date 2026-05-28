import java.util.*;

/**
 * Problem 28: Redundant Connection II (LeetCode 685)
 * 
 * Approach: Directed graph. Handle two cases: node with 2 parents, or cycle.
 * If a node has 2 parents, try removing each candidate edge. Otherwise find cycle edge.
 * Time: O(N), Space: O(N)
 * 
 * Production Analogy: Finding redundant parent in a directed service hierarchy (tree with one extra edge).
 */
public class Problem28_RedundantConnectionII {
    
    public int[] findRedundantDirectedConnection(int[][] edges) {
        int n = edges.length;
        int[] parent = new int[n + 1];
        int[] cand1 = null, cand2 = null;
        // Find node with 2 parents
        for (int[] e : edges) {
            if (parent[e[1]] == 0) parent[e[1]] = e[0];
            else { cand1 = new int[]{parent[e[1]], e[1]}; cand2 = new int[]{e[0], e[1]}; e[1] = 0; } // mark edge invalid
        }
        // Union-Find to detect cycle
        int[] uf = new int[n + 1];
        for (int i = 0; i <= n; i++) uf[i] = i;
        for (int[] e : edges) {
            if (e[1] == 0) continue;
            int pu = find(uf, e[0]), pv = find(uf, e[1]);
            if (pu == pv) return cand1 == null ? e : cand1;
            uf[pu] = pv;
        }
        return cand2;
    }
    
    int find(int[] uf, int x) { return uf[x] == x ? x : (uf[x] = find(uf, uf[x])); }
    
    public static void main(String[] args) {
        Problem28_RedundantConnectionII sol = new Problem28_RedundantConnectionII();
        System.out.println(Arrays.toString(sol.findRedundantDirectedConnection(new int[][]{{1,2},{1,3},{2,3}}))); // [2,3]
        sol = new Problem28_RedundantConnectionII();
        System.out.println(Arrays.toString(sol.findRedundantDirectedConnection(new int[][]{{1,2},{2,3},{3,4},{4,1},{1,5}}))); // [4,1]
    }
}
