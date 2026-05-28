import java.util.*;

/**
 * Problem 14: Critical Connections in a Network (LeetCode 1192) - Bridges
 * 
 * Approach: Tarjan's bridge-finding algorithm using DFS discovery/low times.
 * Time: O(V + E), Space: O(V + E)
 * 
 * Production Analogy: Finding single points of failure in network infrastructure.
 */
public class Problem14_CriticalConnections {
    
    int timer = 0;
    
    public List<List<Integer>> criticalConnections(int n, List<List<Integer>> connections) {
        List<Integer>[] adj = new List[n];
        for (int i = 0; i < n; i++) adj[i] = new ArrayList<>();
        for (List<Integer> c : connections) { adj[c.get(0)].add(c.get(1)); adj[c.get(1)].add(c.get(0)); }
        
        int[] disc = new int[n], low = new int[n];
        Arrays.fill(disc, -1);
        List<List<Integer>> result = new ArrayList<>();
        dfs(0, -1, adj, disc, low, result);
        return result;
    }
    
    void dfs(int u, int parent, List<Integer>[] adj, int[] disc, int[] low, List<List<Integer>> result) {
        disc[u] = low[u] = timer++;
        for (int v : adj[u]) {
            if (v == parent) continue;
            if (disc[v] == -1) {
                dfs(v, u, adj, disc, low, result);
                low[u] = Math.min(low[u], low[v]);
                if (low[v] > disc[u]) result.add(Arrays.asList(u, v));
            } else {
                low[u] = Math.min(low[u], disc[v]);
            }
        }
    }
    
    public static void main(String[] args) {
        Problem14_CriticalConnections sol = new Problem14_CriticalConnections();
        List<List<Integer>> conn = Arrays.asList(Arrays.asList(0,1),Arrays.asList(1,2),Arrays.asList(2,0),Arrays.asList(1,3));
        System.out.println(sol.criticalConnections(4, conn)); // [[1,3]]
    }
}
