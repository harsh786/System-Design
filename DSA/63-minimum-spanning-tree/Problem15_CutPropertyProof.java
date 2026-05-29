import java.util.*;

public class Problem15_CutPropertyProof {
    /*
     * Cut Property Demo: For any cut, the minimum weight crossing edge is in some MST.
     * This demonstrates by finding a cut and verifying the lightest crossing edge is in MST.
     */
    public boolean verifyCutProperty(int n, int[][] edges, boolean[] cutS) {
        // Find minimum crossing edge
        int minCross = Integer.MAX_VALUE, minIdx = -1;
        for (int i = 0; i < edges.length; i++) {
            if (cutS[edges[i][0]] != cutS[edges[i][1]]) {
                if (edges[i][2] < minCross) { minCross = edges[i][2]; minIdx = i; }
            }
        }
        // Build MST and check if this edge is in it
        Arrays.sort(edges, (a,b) -> a[2]-b[2]);
        int[] parent = new int[n]; for (int i = 0; i < n; i++) parent[i] = i;
        Set<String> mstEdges = new HashSet<>();
        for (int[] e : edges) {
            int u = find(parent, e[0]), v = find(parent, e[1]);
            if (u != v) { parent[u] = v; mstEdges.add(Math.min(e[0],e[1])+","+Math.max(e[0],e[1])+","+e[2]); }
        }
        int[] e = edges[minIdx];
        return mstEdges.contains(Math.min(e[0],e[1])+","+Math.max(e[0],e[1])+","+e[2]);
    }
    private int find(int[] p, int x) { return p[x] == x ? x : (p[x] = find(p, p[x])); }

    public static void main(String[] args) {
        Problem15_CutPropertyProof sol = new Problem15_CutPropertyProof();
        int[][] edges = {{0,1,1},{1,2,2},{0,2,3},{2,3,4},{1,3,5}};
        boolean[] cutS = {true, true, false, false}; // S={0,1}, T={2,3}
        System.out.println("Cut property holds: " + sol.verifyCutProperty(4, edges, cutS));
    }
}
