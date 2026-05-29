import java.util.*;

/**
 * Problem 33: Kruskal's Minimum Spanning Tree Algorithm
 * 
 * Classic MST: Sort edges by weight, greedily add edges that don't form cycles.
 * Union-Find efficiently detects cycles.
 * 
 * Time: O(E*logE + E*α(V)), Space: O(V)
 * 
 * Production Analogy: Building minimum cost infrastructure connecting all data centers.
 */
public class Problem33_KruskalMinimumSpanningTree {
    
    int[] parent, rank;
    
    public List<int[]> kruskal(int n, int[][] edges) {
        Arrays.sort(edges, (a, b) -> a[2] - b[2]);
        parent = new int[n]; rank = new int[n];
        for (int i = 0; i < n; i++) parent[i] = i;
        
        List<int[]> mst = new ArrayList<>();
        int totalWeight = 0;
        
        for (int[] e : edges) {
            if (union(e[0], e[1])) {
                mst.add(e);
                totalWeight += e[2];
                if (mst.size() == n - 1) break;
            }
        }
        System.out.println("MST weight: " + totalWeight);
        return mst;
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
        Problem33_KruskalMinimumSpanningTree sol = new Problem33_KruskalMinimumSpanningTree();
        // edges: [u, v, weight]
        int[][] edges = {{0,1,4},{0,7,8},{1,2,8},{1,7,11},{2,3,7},{2,8,2},{2,5,4},{3,4,9},{3,5,14},{4,5,10},{5,6,2},{6,7,1},{6,8,6},{7,8,7}};
        List<int[]> mst = sol.kruskal(9, edges);
        // MST weight: 37
        for (int[] e : mst) System.out.println(e[0] + "-" + e[1] + ": " + e[2]);
    }
}
