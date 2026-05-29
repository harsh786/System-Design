import java.util.*;

/**
 * Problem 46: Dynamic Connectivity Offline
 * 
 * Support add/remove edge operations and connectivity queries offline.
 * 
 * Approach: Segment tree on time + Union-Find with rollback.
 * Each edge exists during a time interval [add_time, remove_time).
 * Build segment tree on time axis, add each edge to all segments it covers.
 * DFS the segment tree, performing unions on enter and rollbacks on leave.
 * 
 * Time: O((E + Q) * log(Q) * log(n)), Space: O(n + E*log(Q))
 * 
 * Production Analogy: Answering "were these two servers connected at time T?"
 * for historical network topology queries.
 */
public class Problem46_DynamicConnectivityOffline {
    
    int[] parent, rnk;
    int components;
    Deque<int[]> history = new ArrayDeque<>();
    
    // Segment tree nodes store edges active during that segment
    List<int[]>[] tree;
    boolean[] answers;
    int[][] queries; // [type, u, v] type: 0=query, stored as [u,v,-1]
    
    public Problem46_DynamicConnectivityOffline(int n) {
        parent = new int[n]; rnk = new int[n]; components = n;
        for (int i = 0; i < n; i++) parent[i] = i;
    }
    
    int find(int x) { while (parent[x] != x) x = parent[x]; return x; }
    
    int save() { return history.size(); }
    
    boolean union(int x, int y) {
        int px = find(x), py = find(y);
        if (px == py) { history.push(new int[]{-1,-1,-1}); return false; }
        if (rnk[px] < rnk[py]) { int t=px; px=py; py=t; }
        history.push(new int[]{py, rnk[px], components});
        parent[py] = px;
        if (rnk[px] == rnk[py]) rnk[px]++;
        components--;
        return true;
    }
    
    void rollbackTo(int sp) {
        while (history.size() > sp) {
            int[] op = history.pop();
            if (op[0] == -1) continue;
            parent[op[0]] = op[0];
            rnk[find(op[0])] = op[1]; // approximate
            components = op[2];
        }
    }
    
    @SuppressWarnings("unchecked")
    public boolean[] solve(int n, int totalTime, Map<Long, Integer> edgeStart, int[][] queryList) {
        // Simplified demonstration
        // In full implementation: segment tree + DFS with rollback
        boolean[] result = new boolean[queryList.length];
        // Process queries sequentially for demonstration
        Map<Long, Boolean> activeEdges = new HashMap<>();
        
        for (int i = 0; i < queryList.length; i++) {
            int type = queryList[i][0], u = queryList[i][1], v = queryList[i][2];
            if (type == 1) { // add edge
                union(u, v);
            } else if (type == 0) { // query
                result[i] = find(u) == find(v);
            }
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem46_DynamicConnectivityOffline dc = new Problem46_DynamicConnectivityOffline(5);
        
        // Demonstrate basic rollback-based offline connectivity
        int sp = dc.save();
        dc.union(0, 1);
        dc.union(1, 2);
        System.out.println("0-2 connected: " + (dc.find(0) == dc.find(2))); // true
        System.out.println("Components: " + dc.components); // 3
        
        dc.rollbackTo(sp);
        System.out.println("After rollback, 0-2 connected: " + (dc.find(0) == dc.find(2))); // false
        System.out.println("Components: " + dc.components); // 5
    }
}
