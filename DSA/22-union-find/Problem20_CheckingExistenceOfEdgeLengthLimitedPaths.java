import java.util.*;

/**
 * Problem 20: Checking Existence of Edge Length Limited Paths (LeetCode 1697)
 * 
 * Given edges with weights and queries [u, v, limit], determine if path exists
 * from u to v using only edges with weight < limit.
 * 
 * Approach: Offline processing. Sort edges by weight, sort queries by limit.
 * Process queries in order of increasing limit, adding qualifying edges.
 * 
 * Time: O(E*logE + Q*logQ + (E+Q)*α(n)), Space: O(n + Q)
 * 
 * Production Analogy: Network SLA queries - "can server A reach server B using
 * only links with latency below X ms?"
 */
public class Problem20_CheckingExistenceOfEdgeLengthLimitedPaths {
    
    int[] parent, rank;
    
    public boolean[] distanceLimitedPathsExist(int n, int[][] edgeList, int[][] queries) {
        parent = new int[n]; rank = new int[n];
        for (int i = 0; i < n; i++) parent[i] = i;
        
        // Sort edges by weight
        Arrays.sort(edgeList, (a, b) -> a[2] - b[2]);
        
        // Sort queries by limit, keeping original index
        int q = queries.length;
        Integer[] idx = new Integer[q];
        for (int i = 0; i < q; i++) idx[i] = i;
        Arrays.sort(idx, (a, b) -> queries[a][2] - queries[b][2]);
        
        boolean[] result = new boolean[q];
        int ei = 0;
        for (int qi : idx) {
            int limit = queries[qi][2];
            while (ei < edgeList.length && edgeList[ei][2] < limit) {
                union(edgeList[ei][0], edgeList[ei][1]);
                ei++;
            }
            result[qi] = find(queries[qi][0]) == find(queries[qi][1]);
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
        Problem20_CheckingExistenceOfEdgeLengthLimitedPaths sol = new Problem20_CheckingExistenceOfEdgeLengthLimitedPaths();
        boolean[] res = sol.distanceLimitedPathsExist(3,
            new int[][]{{0,1,2},{1,2,4},{2,0,8},{1,0,16}},
            new int[][]{{0,1,2},{0,2,5}});
        System.out.println(Arrays.toString(res)); // [false, true]
    }
}
