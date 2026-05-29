import java.util.*;

public class Problem08_SecondBestMST {
    public int secondBestMST(int n, int[][] edges) {
        Arrays.sort(edges, (a,b) -> a[2]-b[2]);
        int[] parent = new int[n]; for (int i = 0; i < n; i++) parent[i] = i;
        List<int[]> mstEdges = new ArrayList<>();
        int mstCost = 0;
        for (int[] e : edges) {
            int u = find(parent, e[0]), v = find(parent, e[1]);
            if (u != v) { parent[u] = v; mstCost += e[2]; mstEdges.add(e); }
        }
        int secondBest = Integer.MAX_VALUE;
        for (int[] exclude : mstEdges) {
            for (int i = 0; i < n; i++) parent[i] = i;
            int cost = 0, count = 0;
            for (int[] e : edges) {
                if (e == exclude) continue;
                int u = find(parent, e[0]), v = find(parent, e[1]);
                if (u != v) { parent[u] = v; cost += e[2]; count++; }
            }
            if (count == n-1) secondBest = Math.min(secondBest, cost);
        }
        return secondBest;
    }

    private int find(int[] p, int x) { return p[x] == x ? x : (p[x] = find(p, p[x])); }

    public static void main(String[] args) {
        Problem08_SecondBestMST sol = new Problem08_SecondBestMST();
        System.out.println(sol.secondBestMST(4, new int[][]{{0,1,1},{0,2,4},{1,2,2},{1,3,5},{2,3,3}})); // 7
    }
}
