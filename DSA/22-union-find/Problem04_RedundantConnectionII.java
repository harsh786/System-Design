import java.util.*;

/**
 * Problem 4: Redundant Connection II (LeetCode 685)
 * 
 * In a rooted directed tree, one additional directed edge is added.
 * Find the edge to remove to restore a valid rooted tree.
 * 
 * Three cases:
 * 1. A node has two parents (indegree 2), no cycle -> remove the later edge to that node
 * 2. A node has two parents AND there's a cycle -> remove the edge in cycle that points to that node
 * 3. No node has two parents, but there's a cycle -> find the cycle edge (like Problem 3)
 * 
 * Time: O(n * α(n)), Space: O(n)
 * 
 * Production Analogy: In a microservice dependency tree, each service should have
 * exactly one "owner" (parent). A redundant connection II scenario represents
 * either a circular dependency or dual ownership that needs resolution.
 */
public class Problem04_RedundantConnectionII {
    
    int[] parent, rank;
    
    public int[] findRedundantDirectedConnection(int[][] edges) {
        int n = edges.length;
        int[] indegree = new int[n + 1];
        int nodeWithTwoParents = -1;
        int[] candidate1 = null, candidate2 = null;
        
        // Find node with indegree 2
        for (int[] e : edges) {
            indegree[e[1]]++;
            if (indegree[e[1]] == 2) nodeWithTwoParents = e[1];
        }
        
        if (nodeWithTwoParents != -1) {
            // Find the two edges pointing to this node
            for (int i = edges.length - 1; i >= 0; i--) {
                if (edges[i][1] == nodeWithTwoParents) {
                    if (candidate1 == null) candidate1 = edges[i];
                    else candidate2 = edges[i];
                }
            }
            // Try removing candidate1 (later occurrence), check if valid tree
            parent = new int[n + 1]; rank = new int[n + 1];
            for (int i = 0; i <= n; i++) parent[i] = i;
            for (int[] e : edges) {
                if (e == candidate1) continue;
                if (!union(e[0], e[1])) return candidate2; // cycle exists, remove other
            }
            return candidate1;
        }
        
        // No node with 2 parents - just find cycle edge (case 3)
        parent = new int[n + 1]; rank = new int[n + 1];
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
        Problem04_RedundantConnectionII sol = new Problem04_RedundantConnectionII();
        
        // Test 1: node 3 has two parents
        System.out.println(Arrays.toString(
            sol.findRedundantDirectedConnection(new int[][]{{1,2},{1,3},{2,3}}))); // [2,3]
        
        // Test 2: cycle without two parents
        System.out.println(Arrays.toString(
            sol.findRedundantDirectedConnection(new int[][]{{1,2},{2,3},{3,4},{4,1},{1,5}}))); // [4,1]
    }
}
