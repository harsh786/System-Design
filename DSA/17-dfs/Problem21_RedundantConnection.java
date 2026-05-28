import java.util.*;

/**
 * Problem: Redundant Connection (LeetCode 684)
 * Approach: Union-Find (DFS alternative: check if adding edge creates cycle)
 * Time: O(N*alpha(N)) ≈ O(N), Space: O(N)
 * Production Analogy: Detecting redundant network links that create loops in spanning tree protocols
 */
public class Problem21_RedundantConnection {
    int[] parent, rank;

    public int[] findRedundantConnection(int[][] edges) {
        int n = edges.length;
        parent = new int[n + 1]; rank = new int[n + 1];
        for (int i = 0; i <= n; i++) parent[i] = i;
        for (int[] e : edges) {
            if (!union(e[0], e[1])) return e;
        }
        return new int[0];
    }

    private int find(int x) { return parent[x] == x ? x : (parent[x] = find(parent[x])); }

    private boolean union(int a, int b) {
        int pa = find(a), pb = find(b);
        if (pa == pb) return false;
        if (rank[pa] < rank[pb]) parent[pa] = pb;
        else if (rank[pa] > rank[pb]) parent[pb] = pa;
        else { parent[pb] = pa; rank[pa]++; }
        return true;
    }

    public static void main(String[] args) {
        int[][] edges = {{1,2},{1,3},{2,3}};
        System.out.println(Arrays.toString(new Problem21_RedundantConnection().findRedundantConnection(edges)));
    }
}
