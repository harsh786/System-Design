import java.util.*;

/**
 * Problem 39: Graph Connectivity With Threshold (LeetCode 1627)
 * 
 * Cities 1..n. Two cities connected if they share a common divisor > threshold.
 * Answer connectivity queries.
 * 
 * Approach: For each divisor d > threshold, union all multiples of d.
 * 
 * Time: O(n*log(n)*α(n) + Q*α(n)), Space: O(n)
 * 
 * Production Analogy: Resource sharing groups - services sharing a common resource pool
 * (above a minimum size threshold) are considered connected.
 */
public class Problem39_GraphConnectivityWithThreshold {
    
    int[] parent, rank;
    
    public List<Boolean> areConnected(int n, int threshold, int[][] queries) {
        parent = new int[n + 1]; rank = new int[n + 1];
        for (int i = 0; i <= n; i++) parent[i] = i;
        
        for (int d = threshold + 1; d <= n; d++) {
            for (int mult = 2 * d; mult <= n; mult += d) {
                union(d, mult);
            }
        }
        
        List<Boolean> result = new ArrayList<>();
        for (int[] q : queries) {
            result.add(find(q[0]) == find(q[1]));
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
        Problem39_GraphConnectivityWithThreshold sol = new Problem39_GraphConnectivityWithThreshold();
        System.out.println(sol.areConnected(6, 2, new int[][]{{1,4},{2,5},{3,6}})); // [false, false, true]
        System.out.println(sol.areConnected(6, 0, new int[][]{{4,5},{3,4},{3,2},{2,6},{1,3}})); // [true,true,true,true,true]
    }
}
