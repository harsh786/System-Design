import java.util.*;

/**
 * Problem 42: Count Unreachable Pairs of Nodes (LeetCode 2316)
 * 
 * Count pairs of nodes that cannot reach each other.
 * 
 * Approach: Find component sizes. For each component of size s,
 * it contributes s * (n - s) unreachable pairs (but each counted twice -> use running sum).
 * 
 * Time: O(n + E*α(n)), Space: O(n)
 * 
 * Production Analogy: Measuring network fragmentation - how many service pairs
 * are unable to communicate due to partitions?
 */
public class Problem42_CountUnreachablePairsOfNodes {
    
    int[] parent, rank, size;
    
    public long countPairs(int n, int[][] edges) {
        parent = new int[n]; rank = new int[n]; size = new int[n];
        for (int i = 0; i < n; i++) { parent[i] = i; size[i] = 1; }
        
        for (int[] e : edges) union(e[0], e[1]);
        
        // Collect component sizes
        Map<Integer, Integer> compSizes = new HashMap<>();
        for (int i = 0; i < n; i++) compSizes.put(find(i), size[find(i)]);
        
        long result = 0, sumSoFar = 0;
        for (int s : compSizes.values()) {
            result += sumSoFar * s;
            sumSoFar += s;
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
        if (rank[px] < rank[py]) { parent[px] = py; size[py] += size[px]; }
        else if (rank[px] > rank[py]) { parent[py] = px; size[px] += size[py]; }
        else { parent[py] = px; size[px] += size[py]; rank[px]++; }
    }
    
    public static void main(String[] args) {
        Problem42_CountUnreachablePairsOfNodes sol = new Problem42_CountUnreachablePairsOfNodes();
        System.out.println(sol.countPairs(3, new int[][]{{0,1},{0,2},{1,2}})); // 0
        
        sol = new Problem42_CountUnreachablePairsOfNodes();
        System.out.println(sol.countPairs(7, new int[][]{{0,2},{0,5},{2,4},{1,6},{5,4}})); // 14
    }
}
