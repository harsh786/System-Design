import java.util.*;

public class Problem09_BottleneckSpanningTree {
    /* MST is also a bottleneck spanning tree - max edge in MST is minimized */
    public int bottleneckEdge(int n, int[][] edges) {
        Arrays.sort(edges, (a,b) -> a[2]-b[2]);
        int[] parent = new int[n]; for (int i = 0; i < n; i++) parent[i] = i;
        int maxEdge = 0;
        for (int[] e : edges) {
            int u = find(parent, e[0]), v = find(parent, e[1]);
            if (u != v) { parent[u] = v; maxEdge = Math.max(maxEdge, e[2]); }
        }
        return maxEdge;
    }

    private int find(int[] p, int x) { return p[x] == x ? x : (p[x] = find(p, p[x])); }

    public static void main(String[] args) {
        Problem09_BottleneckSpanningTree sol = new Problem09_BottleneckSpanningTree();
        System.out.println(sol.bottleneckEdge(4, new int[][]{{0,1,1},{0,2,4},{1,2,2},{1,3,5},{2,3,3}})); // 3
    }
}
