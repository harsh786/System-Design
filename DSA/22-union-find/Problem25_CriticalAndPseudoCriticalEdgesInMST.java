import java.util.*;

/**
 * Problem 25: Find Critical and Pseudo-Critical Edges in MST (LeetCode 1489)
 * 
 * Critical edge: removing it increases MST weight.
 * Pseudo-critical: appears in some MST but not all.
 * 
 * Approach: For each edge, check if MST without it costs more (critical).
 * If not critical, check if forcing it still achieves same MST cost (pseudo-critical).
 * 
 * Time: O(E² * α(V)), Space: O(V + E)
 * 
 * Production Analogy: Identifying critical vs redundant network links -
 * which links MUST stay for minimum-cost connectivity vs which are alternatives.
 */
public class Problem25_CriticalAndPseudoCriticalEdgesInMST {
    
    int[] parent, rank;
    
    public List<List<Integer>> findCriticalAndPseudoCriticalEdges(int n, int[][] edges) {
        int m = edges.length;
        int[][] indexed = new int[m][4]; // u, v, w, original index
        for (int i = 0; i < m; i++) { indexed[i] = new int[]{edges[i][0], edges[i][1], edges[i][2], i}; }
        Arrays.sort(indexed, (a, b) -> a[2] - b[2]);
        
        int mstWeight = buildMST(n, indexed, -1, -1);
        
        List<Integer> critical = new ArrayList<>(), pseudo = new ArrayList<>();
        for (int i = 0; i < m; i++) {
            // Check critical: exclude edge i
            if (buildMST(n, indexed, i, -1) > mstWeight) {
                critical.add(indexed[i][3]);
            } else if (buildMST(n, indexed, -1, i) == mstWeight) {
                pseudo.add(indexed[i][3]);
            }
        }
        return Arrays.asList(critical, pseudo);
    }
    
    private int buildMST(int n, int[][] edges, int exclude, int include) {
        parent = new int[n]; rank = new int[n];
        for (int i = 0; i < n; i++) parent[i] = i;
        int weight = 0, count = 0;
        
        if (include != -1) {
            weight += edges[include][2];
            union(edges[include][0], edges[include][1]);
            count++;
        }
        
        for (int i = 0; i < edges.length; i++) {
            if (i == exclude) continue;
            if (union(edges[i][0], edges[i][1])) {
                weight += edges[i][2];
                if (++count == n - 1) break;
            }
        }
        return count == n - 1 ? weight : Integer.MAX_VALUE;
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
        Problem25_CriticalAndPseudoCriticalEdgesInMST sol = new Problem25_CriticalAndPseudoCriticalEdgesInMST();
        System.out.println(sol.findCriticalAndPseudoCriticalEdges(5, new int[][]{
            {0,1,1},{1,2,1},{2,3,2},{0,3,2},{0,4,3},{3,4,3},{1,4,6}}));
        // [[0,1],[2,3,4,5]]
    }
}
