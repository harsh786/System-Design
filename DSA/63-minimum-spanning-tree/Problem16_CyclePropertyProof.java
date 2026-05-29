import java.util.*;

public class Problem16_CyclePropertyProof {
    /*
     * Cycle Property: The maximum weight edge in any cycle is not in some MST.
     */
    public boolean verifyCycleProperty(int n, int[][] edges, int[] cycle) {
        // Find max weight edge in cycle
        int maxWeight = 0, maxU = -1, maxV = -1;
        for (int i = 0; i < cycle.length; i++) {
            int u = cycle[i], v = cycle[(i+1) % cycle.length];
            for (int[] e : edges) {
                if ((e[0]==u && e[1]==v) || (e[0]==v && e[1]==u)) {
                    if (e[2] > maxWeight) { maxWeight = e[2]; maxU = u; maxV = v; }
                }
            }
        }
        // Check MST doesn't contain this edge (or can be built without it)
        Arrays.sort(edges, (a,b) -> a[2]-b[2]);
        int[] parent = new int[n]; for (int i = 0; i < n; i++) parent[i] = i;
        boolean maxEdgeInMST = false;
        for (int[] e : edges) {
            int u = find(parent, e[0]), v = find(parent, e[1]);
            if (u != v) { parent[u] = v; if (e[2]==maxWeight && ((e[0]==maxU&&e[1]==maxV)||(e[0]==maxV&&e[1]==maxU))) maxEdgeInMST = true; }
        }
        return !maxEdgeInMST;
    }
    private int find(int[] p, int x) { return p[x] == x ? x : (p[x] = find(p, p[x])); }

    public static void main(String[] args) {
        Problem16_CyclePropertyProof sol = new Problem16_CyclePropertyProof();
        int[][] edges = {{0,1,1},{1,2,2},{0,2,3},{2,3,4},{1,3,5}};
        System.out.println("Cycle property (0-1-2): " + sol.verifyCycleProperty(4, edges, new int[]{0,1,2}));
    }
}
