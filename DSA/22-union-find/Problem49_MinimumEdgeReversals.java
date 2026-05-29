import java.util.*;

/**
 * Problem 49: Minimum Edge Reversals So Every Node Is Reachable (LeetCode 2858)
 * 
 * Directed tree with n nodes. For each node, find minimum edge reversals needed
 * so that every other node can reach it.
 * 
 * Approach: Root tree at node 0, count reversals needed for 0.
 * Then re-root: moving root from parent to child changes count by +1 or -1
 * depending on edge direction.
 * 
 * Note: This is primarily a DFS/re-rooting problem. Union-Find can help build
 * the tree structure, but the main logic uses DFS.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: In a content delivery network with directional links,
 * find how many links need reversing for each node to become the origin server.
 */
public class Problem49_MinimumEdgeReversals {
    
    List<int[]>[] adj; // [neighbor, weight] weight=0 if forward edge, 1 if needs reversal
    int[] result;
    
    public int[] minEdgeReversals(int n, int[][] edges) {
        adj = new ArrayList[n];
        for (int i = 0; i < n; i++) adj[i] = new ArrayList<>();
        
        for (int[] e : edges) {
            adj[e[0]].add(new int[]{e[1], 0}); // forward: no reversal needed
            adj[e[1]].add(new int[]{e[0], 1}); // backward: reversal needed
        }
        
        result = new int[n];
        // DFS from node 0 to count reversals needed for 0
        result[0] = dfs1(0, -1);
        // Re-root DFS
        dfs2(0, -1);
        return result;
    }
    
    private int dfs1(int node, int parent) {
        int count = 0;
        for (int[] next : adj[node]) {
            if (next[0] != parent) {
                count += next[1] + dfs1(next[0], node);
            }
        }
        return count;
    }
    
    private void dfs2(int node, int parent) {
        for (int[] next : adj[node]) {
            if (next[0] != parent) {
                // If edge node->next is forward (cost 0 for node), reversing root means +1 for next
                // If edge node->next is backward (cost 1 for node), reversing root means -1 for next
                result[next[0]] = result[node] + (next[1] == 0 ? 1 : -1);
                dfs2(next[0], node);
            }
        }
    }
    
    public static void main(String[] args) {
        Problem49_MinimumEdgeReversals sol = new Problem49_MinimumEdgeReversals();
        System.out.println(Arrays.toString(sol.minEdgeReversals(4, new int[][]{{2,0},{2,1},{1,3}}))); // [1,1,0,2]
        
        sol = new Problem49_MinimumEdgeReversals();
        System.out.println(Arrays.toString(sol.minEdgeReversals(3, new int[][]{{1,2},{2,0}}))); // [2,0,1]
    }
}
