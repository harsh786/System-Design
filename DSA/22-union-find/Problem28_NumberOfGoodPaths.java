import java.util.*;

/**
 * Problem 28: Number of Good Paths (LeetCode 2421)
 * 
 * A good path starts and ends at nodes with the same value, and all nodes
 * on the path have values <= the endpoints. Count good paths.
 * 
 * Approach: Process nodes in increasing order of value. For each group of same-value nodes,
 * union them with their neighbors that have already been processed (smaller values).
 * Count pairs within same component that have the current value.
 * 
 * Time: O(n * α(n) + n*log(n)), Space: O(n)
 * 
 * Production Analogy: Peer-to-peer routing where messages can only traverse nodes
 * with priority <= sender. Count valid sender-receiver pairs.
 */
public class Problem28_NumberOfGoodPaths {
    
    int[] parent, rank;
    
    public int numberOfGoodPaths(int[] vals, int[][] edges) {
        int n = vals.length;
        parent = new int[n]; rank = new int[n];
        for (int i = 0; i < n; i++) parent[i] = i;
        
        // Build adjacency list
        List<List<Integer>> adj = new ArrayList<>();
        for (int i = 0; i < n; i++) adj.add(new ArrayList<>());
        for (int[] e : edges) { adj.get(e[0]).add(e[1]); adj.get(e[1]).add(e[0]); }
        
        // Group nodes by value
        TreeMap<Integer, List<Integer>> valueToNodes = new TreeMap<>();
        for (int i = 0; i < n; i++) valueToNodes.computeIfAbsent(vals[i], k -> new ArrayList<>()).add(i);
        
        int result = 0;
        for (var entry : valueToNodes.entrySet()) {
            int val = entry.getKey();
            List<Integer> nodes = entry.getValue();
            
            // Union each node with neighbors that have value <= val
            for (int node : nodes) {
                for (int neighbor : adj.get(node)) {
                    if (vals[neighbor] <= val) union(node, neighbor);
                }
            }
            
            // Count pairs in same component
            Map<Integer, Integer> componentCount = new HashMap<>();
            for (int node : nodes) {
                componentCount.merge(find(node), 1, Integer::sum);
            }
            for (int count : componentCount.values()) {
                result += count * (count + 1) / 2; // pairs + single nodes
            }
        }
        return result;
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
        Problem28_NumberOfGoodPaths sol = new Problem28_NumberOfGoodPaths();
        System.out.println(sol.numberOfGoodPaths(new int[]{1,3,2,1,3},
            new int[][]{{0,1},{0,2},{2,3},{2,4}})); // 6
        System.out.println(sol.numberOfGoodPaths(new int[]{1,1,2,2,3},
            new int[][]{{0,1},{1,2},{2,3},{3,4}})); // 7
    }
}
