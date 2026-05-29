import java.util.*;

public class Problem19_InteractiveLCA {
    // Interactive LCA - query parent of node
    static int[] parent = {-1, 0, 0, 1, 1, 2, 2}; // tree structure
    
    static int getParent(int node) { return parent[node]; }
    
    static int findLCA(int u, int v) {
        Set<Integer> ancestors = new HashSet<>();
        while (u != -1) { ancestors.add(u); u = getParent(u); }
        while (v != -1) { if (ancestors.contains(v)) return v; v = getParent(v); }
        return -1;
    }
    
    public static void main(String[] args) {
        System.out.println("LCA(4,5): " + findLCA(4, 5)); // 0
        System.out.println("LCA(3,4): " + findLCA(3, 4)); // 1
    }
}
