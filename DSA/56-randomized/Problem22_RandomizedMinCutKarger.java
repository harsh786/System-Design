import java.util.*;

public class Problem22_RandomizedMinCutKarger {
    // Karger's algorithm: contract random edges until 2 vertices remain
    public static int kargerMinCut(int n, int[][] edges) {
        Random rand = new Random();
        int minCut = Integer.MAX_VALUE;
        int trials = n * n; // repeat for high probability
        for (int t = 0; t < trials; t++) {
            int[] parent = new int[n];
            for (int i = 0; i < n; i++) parent[i] = i;
            int vertices = n;
            List<int[]> edgeList = new ArrayList<>();
            for (int[] e : edges) edgeList.add(e.clone());
            while (vertices > 2) {
                int idx = rand.nextInt(edgeList.size());
                int u = find(parent, edgeList.get(idx)[0]);
                int v = find(parent, edgeList.get(idx)[1]);
                if (u == v) { edgeList.remove(idx); continue; }
                parent[v] = u;
                vertices--;
                edgeList.remove(idx);
            }
            int cut = 0;
            for (int[] e : edgeList) if (find(parent, e[0]) != find(parent, e[1])) cut++;
            minCut = Math.min(minCut, cut);
        }
        return minCut;
    }

    static int find(int[] parent, int x) { return parent[x] == x ? x : (parent[x] = find(parent, parent[x])); }

    public static void main(String[] args) {
        int[][] edges = {{0,1},{0,2},{1,2},{1,3},{2,3}};
        System.out.println("Min cut: " + kargerMinCut(4, edges));
    }
}
