import java.util.*;

public class Problem19_MSTVerification {
    /* Verify if given tree is an MST by checking no non-tree edge can improve it */
    public boolean isMST(int n, int[][] allEdges, int[][] treeEdges) {
        // Build adjacency for tree
        List<int[]>[] adj = new List[n];
        for (int i = 0; i < n; i++) adj[i] = new ArrayList<>();
        for (int[] e : treeEdges) { adj[e[0]].add(new int[]{e[1],e[2]}); adj[e[1]].add(new int[]{e[0],e[2]}); }
        Set<String> treeSet = new HashSet<>();
        for (int[] e : treeEdges) treeSet.add(Math.min(e[0],e[1])+","+Math.max(e[0],e[1]));
        for (int[] e : allEdges) {
            String key = Math.min(e[0],e[1])+","+Math.max(e[0],e[1]);
            if (treeSet.contains(key)) continue;
            int maxEdge = maxEdgeOnPath(adj, n, e[0], e[1]);
            if (e[2] < maxEdge) return false;
        }
        return true;
    }

    private int maxEdgeOnPath(List<int[]>[] adj, int n, int src, int dst) {
        int[] maxTo = new int[n]; Arrays.fill(maxTo, -1); maxTo[src] = 0;
        Queue<Integer> q = new LinkedList<>(); q.add(src);
        while (!q.isEmpty()) {
            int u = q.poll();
            for (int[] nei : adj[u]) {
                if (maxTo[nei[0]] == -1) { maxTo[nei[0]] = Math.max(maxTo[u], nei[1]); q.add(nei[0]); }
            }
        }
        return maxTo[dst];
    }

    public static void main(String[] args) {
        Problem19_MSTVerification sol = new Problem19_MSTVerification();
        int[][] all = {{0,1,1},{0,2,4},{1,2,2},{1,3,5},{2,3,3}};
        int[][] tree = {{0,1,1},{1,2,2},{2,3,3}};
        System.out.println("Is MST: " + sol.isMST(4, all, tree));
    }
}
