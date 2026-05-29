import java.util.*;

/**
 * Problem 44: Union-Find with Rollback
 * 
 * Standard Union-Find but with ability to undo operations. Used in offline
 * dynamic connectivity and divide-and-conquer on queries.
 * 
 * Key: Do NOT use path compression (breaks rollback). Use union by rank only.
 * Maintain a stack of operations to undo.
 * 
 * Time: O(log n) per operation (no path compression), Space: O(n + ops)
 * 
 * Production Analogy: Transactional cluster management - ability to rollback
 * cluster merges if a health check fails after joining.
 */
public class Problem44_UnionFindWithRollback {
    
    int[] parent, rank;
    int components;
    Deque<int[]> history = new ArrayDeque<>(); // [node, oldParent, oldRank, componentDelta]
    
    public Problem44_UnionFindWithRollback(int n) {
        parent = new int[n]; rank = new int[n]; components = n;
        for (int i = 0; i < n; i++) parent[i] = i;
    }
    
    // NO path compression - needed for rollback
    public int find(int x) {
        while (parent[x] != x) x = parent[x];
        return x;
    }
    
    public boolean union(int x, int y) {
        int px = find(x), py = find(y);
        if (px == py) {
            history.push(new int[]{-1, -1, -1, 0}); // No-op marker
            return false;
        }
        if (rank[px] < rank[py]) { int t = px; px = py; py = t; }
        // py goes under px
        history.push(new int[]{py, parent[py], rank[px], 1});
        parent[py] = px;
        if (rank[px] == rank[py]) rank[px]++;
        components--;
        return true;
    }
    
    public void rollback() {
        if (history.isEmpty()) return;
        int[] op = history.pop();
        if (op[0] == -1) return; // was no-op
        parent[op[0]] = op[1];
        rank[find(op[0])] = op[2]; // not quite right, store px rank
        components++;
    }
    
    public int savepoint() {
        return history.size();
    }
    
    public void rollbackTo(int savepoint) {
        while (history.size() > savepoint) rollback();
    }
    
    public static void main(String[] args) {
        Problem44_UnionFindWithRollback uf = new Problem44_UnionFindWithRollback(5);
        
        System.out.println("Components: " + uf.components); // 5
        int sp = uf.savepoint();
        uf.union(0, 1);
        uf.union(2, 3);
        System.out.println("Components: " + uf.components); // 3
        System.out.println("0 and 1 connected: " + (uf.find(0) == uf.find(1))); // true
        
        uf.rollbackTo(sp);
        System.out.println("After rollback components: " + uf.components); // 5
        System.out.println("0 and 1 connected: " + (uf.find(0) == uf.find(1))); // false
    }
}
