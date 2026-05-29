import java.util.*;

public class Problem20_MSTUniqueness {
    public boolean isMSTUnique(int n, int[][] edges) {
        Arrays.sort(edges, (a,b) -> a[2]-b[2]);
        int[] parent = new int[n]; for (int i = 0; i < n; i++) parent[i] = i;
        int mstCost = 0;
        List<int[]> mstEdges = new ArrayList<>();
        for (int[] e : edges) {
            int u = find(parent, e[0]), v = find(parent, e[1]);
            if (u != v) { parent[u] = v; mstCost += e[2]; mstEdges.add(e); }
        }
        // Try removing each MST edge and rebuilding
        for (int[] exclude : mstEdges) {
            for (int i = 0; i < n; i++) parent[i] = i;
            int cost = 0, count = 0;
            for (int[] e : edges) {
                if (e == exclude) continue;
                int u = find(parent, e[0]), v = find(parent, e[1]);
                if (u != v) { parent[u] = v; cost += e[2]; count++; }
            }
            if (count == n-1 && cost == mstCost) return false; // another MST exists
        }
        return true;
    }
    private int find(int[] p, int x) { return p[x] == x ? x : (p[x] = find(p, p[x])); }

    public static void main(String[] args) {
        Problem20_MSTUniqueness sol = new Problem20_MSTUniqueness();
        System.out.println(sol.isMSTUnique(4, new int[][]{{0,1,1},{0,2,2},{1,2,2},{1,3,3},{2,3,3}})); // false
    }
}
