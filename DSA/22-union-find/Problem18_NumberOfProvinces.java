import java.util.*;

/**
 * Problem 18: Number of Provinces (LeetCode 547)
 * 
 * Given adjacency matrix of cities, find number of provinces (connected components).
 * 
 * Time: O(n² * α(n)), Space: O(n)
 * 
 * Production Analogy: Identifying isolated VPCs/network segments in a cloud environment.
 */
public class Problem18_NumberOfProvinces {
    
    int[] parent, rank;
    
    public int findCircleNum(int[][] isConnected) {
        int n = isConnected.length;
        parent = new int[n]; rank = new int[n];
        for (int i = 0; i < n; i++) parent[i] = i;
        int components = n;
        
        for (int i = 0; i < n; i++)
            for (int j = i + 1; j < n; j++)
                if (isConnected[i][j] == 1) {
                    int pi = find(i), pj = find(j);
                    if (pi != pj) {
                        if (rank[pi] < rank[pj]) parent[pi] = pj;
                        else if (rank[pi] > rank[pj]) parent[pj] = pi;
                        else { parent[pj] = pi; rank[pi]++; }
                        components--;
                    }
                }
        return components;
    }
    
    private int find(int x) {
        if (parent[x] != x) parent[x] = find(parent[x]);
        return parent[x];
    }
    
    public static void main(String[] args) {
        Problem18_NumberOfProvinces sol = new Problem18_NumberOfProvinces();
        System.out.println(sol.findCircleNum(new int[][]{{1,1,0},{1,1,0},{0,0,1}})); // 2
        System.out.println(sol.findCircleNum(new int[][]{{1,0,0},{0,1,0},{0,0,1}})); // 3
    }
}
