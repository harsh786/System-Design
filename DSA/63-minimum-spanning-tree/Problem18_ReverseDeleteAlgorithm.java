import java.util.*;

public class Problem18_ReverseDeleteAlgorithm {
    public int reverseDeleteMST(int n, int[][] edges) {
        List<int[]> sorted = new ArrayList<>(Arrays.asList(edges));
        sorted.sort((a,b) -> b[2]-a[2]); // sort descending
        List<int[]> remaining = new ArrayList<>(sorted);
        for (int[] e : sorted) {
            remaining.remove(e);
            if (!isConnected(n, remaining)) remaining.add(e);
        }
        int cost = 0;
        for (int[] e : remaining) cost += e[2];
        return cost;
    }

    private boolean isConnected(int n, List<int[]> edges) {
        int[] parent = new int[n]; for (int i = 0; i < n; i++) parent[i] = i;
        for (int[] e : edges) { int u = find(parent, e[0]), v = find(parent, e[1]); if (u != v) parent[u] = v; }
        int root = find(parent, 0);
        for (int i = 1; i < n; i++) if (find(parent, i) != root) return false;
        return true;
    }
    private int find(int[] p, int x) { return p[x] == x ? x : (p[x] = find(p, p[x])); }

    public static void main(String[] args) {
        Problem18_ReverseDeleteAlgorithm sol = new Problem18_ReverseDeleteAlgorithm();
        System.out.println(sol.reverseDeleteMST(4, new int[][]{{0,1,1},{0,2,4},{1,2,2},{1,3,5},{2,3,3}})); // 6
    }
}
