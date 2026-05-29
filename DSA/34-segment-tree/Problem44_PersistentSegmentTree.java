package segmenttree;

/**
 * Problem 44: Persistent Segment Tree (Concept)
 * 
 * Approach: Each update creates a new root with path-copied nodes.
 * Enables querying any historical version of the tree.
 * 
 * Time Complexity: O(log n) per update/query
 * Space Complexity: O(n + q*log n) for q updates
 */
public class Problem44_PersistentSegmentTree {
    
    static int[] lc, rc, val;
    static int cnt = 0;
    static int[] roots;
    
    static int newNode() { return ++cnt; }
    
    static int build(int s, int e) {
        int o = newNode();
        if (s == e) return o;
        int mid = (s + e) / 2;
        lc[o] = build(s, mid);
        rc[o] = build(mid + 1, e);
        val[o] = val[lc[o]] + val[rc[o]];
        return o;
    }
    
    static int update(int prev, int s, int e, int idx, int delta) {
        int o = newNode();
        lc[o] = lc[prev]; rc[o] = rc[prev]; val[o] = val[prev] + delta;
        if (s == e) return o;
        int mid = (s + e) / 2;
        if (idx <= mid) lc[o] = update(lc[prev], s, mid, idx, delta);
        else rc[o] = update(rc[prev], mid + 1, e, idx, delta);
        val[o] = val[lc[o]] + val[rc[o]];
        return o;
    }
    
    static int query(int o, int s, int e, int l, int r) {
        if (r < s || e < l) return 0;
        if (l <= s && e <= r) return val[o];
        int mid = (s + e) / 2;
        return query(lc[o], s, mid, l, r) + query(rc[o], mid + 1, e, l, r);
    }
    
    public static void main(String[] args) {
        int n = 5, maxNodes = 200000;
        lc = new int[maxNodes]; rc = new int[maxNodes]; val = new int[maxNodes];
        roots = new int[n + 1];
        
        roots[0] = build(0, n - 1);
        // Version 1: set index 2 to +5
        roots[1] = update(roots[0], 0, n - 1, 2, 5);
        // Version 2: set index 4 to +3
        roots[2] = update(roots[1], 0, n - 1, 4, 3);
        
        System.out.println(query(roots[0], 0, n - 1, 0, 4)); // 0
        System.out.println(query(roots[1], 0, n - 1, 0, 4)); // 5
        System.out.println(query(roots[2], 0, n - 1, 0, 4)); // 8
        System.out.println(query(roots[1], 0, n - 1, 4, 4)); // 0 (version 1 has no update at 4)
    }
}
