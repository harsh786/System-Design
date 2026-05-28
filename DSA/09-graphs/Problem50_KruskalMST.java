import java.util.*;

/**
 * Problem 50: Kruskal's MST Algorithm
 * 
 * Approach: Sort edges by weight. Use Union-Find to add edges that don't create cycles.
 * Time: O(E log E), Space: O(V)
 * 
 * Production Analogy: Building minimum-cost network backbone connecting all data centers.
 */
public class Problem50_KruskalMST {
    
    int[] parent, rank;
    int find(int x) { return parent[x] == x ? x : (parent[x] = find(parent[x])); }
    boolean union(int a, int b) { int pa=find(a),pb=find(b); if(pa==pb)return false;
        if(rank[pa]<rank[pb])parent[pa]=pb; else if(rank[pa]>rank[pb])parent[pb]=pa; else{parent[pb]=pa;rank[pa]++;}return true;}
    
    public int[][] kruskal(int n, int[][] edges) {
        parent = new int[n]; rank = new int[n];
        for (int i = 0; i < n; i++) parent[i] = i;
        Arrays.sort(edges, (a,b) -> a[2] - b[2]);
        List<int[]> mst = new ArrayList<>();
        int totalWeight = 0;
        for (int[] e : edges) {
            if (union(e[0], e[1])) { mst.add(e); totalWeight += e[2]; if (mst.size() == n-1) break; }
        }
        System.out.println("MST total weight: " + totalWeight);
        return mst.toArray(new int[0][]);
    }
    
    public static void main(String[] args) {
        Problem50_KruskalMST sol = new Problem50_KruskalMST();
        // 4 nodes, 5 edges
        int[][] edges = {{0,1,10},{0,2,6},{0,3,5},{1,3,15},{2,3,4}};
        int[][] mst = sol.kruskal(4, edges);
        for (int[] e : mst) System.out.println(Arrays.toString(e));
        // Expected MST weight: 19 (edges: 2-3:4, 0-3:5, 0-1:10)
        
        System.out.println("---");
        sol = new Problem50_KruskalMST();
        int[][] edges2 = {{0,1,1},{1,2,2},{0,2,3},{2,3,4},{3,4,5},{0,4,10}};
        int[][] mst2 = sol.kruskal(5, edges2);
        for (int[] e : mst2) System.out.println(Arrays.toString(e));
    }
}
