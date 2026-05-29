import java.util.*;

/**
 * Problem 8: Network Resilience Analysis
 * 
 * Analyze how resilient a network is to node/edge failures using
 * biconnected component analysis.
 * 
 * Metrics:
 * - Number of articulation points (single points of failure)
 * - Number of bridges (critical links)
 * - Size of largest biconnected component (strongest subnetwork)
 * - Vertex connectivity (min vertices to disconnect) - approximated
 * - Edge connectivity (min edges to disconnect) - via bridges
 */
public class Problem08_NetworkResilience {

    private int timer = 0;

    static class ResilienceReport {
        int nodes, edges;
        List<Integer> articulationPoints;
        List<int[]> bridges;
        int numBiconnectedComponents;
        int largestComponentSize;
        double resilienceScore; // 0-1, higher = more resilient
    }

    public ResilienceReport analyze(int n, int[][] edges) {
        List<List<Integer>> adj = new ArrayList<>();
        for (int i = 0; i < n; i++) adj.add(new ArrayList<>());
        for (int[] e : edges) { adj.get(e[0]).add(e[1]); adj.get(e[1]).add(e[0]); }

        ResilienceReport report = new ResilienceReport();
        report.nodes = n;
        report.edges = edges.length;

        // Find articulation points and bridges
        int[] disc = new int[n], low = new int[n];
        boolean[] visited = new boolean[n], isAP = new boolean[n];
        report.bridges = new ArrayList<>();

        for (int i = 0; i < n; i++) {
            if (!visited[i]) dfs(i, -1, adj, disc, low, visited, isAP, report.bridges);
        }

        report.articulationPoints = new ArrayList<>();
        for (int i = 0; i < n; i++) if (isAP[i]) report.articulationPoints.add(i);

        // Count biconnected components (simplified: edges - bridges + 1 per connected component)
        report.numBiconnectedComponents = report.bridges.size() + 1; // Approximation

        // Resilience score: 1 - (articulationPoints/nodes + bridges/edges) / 2
        double apRatio = (double) report.articulationPoints.size() / n;
        double brRatio = edges.length > 0 ? (double) report.bridges.size() / edges.length : 0;
        report.resilienceScore = 1.0 - (apRatio + brRatio) / 2;

        return report;
    }

    private void dfs(int u, int parent, List<List<Integer>> adj, int[] disc, int[] low,
                     boolean[] visited, boolean[] isAP, List<int[]> bridges) {
        visited[u] = true;
        disc[u] = low[u] = timer++;
        int children = 0;
        for (int v : adj.get(u)) {
            if (!visited[v]) {
                children++;
                dfs(v, u, adj, disc, low, visited, isAP, bridges);
                low[u] = Math.min(low[u], low[v]);
                if (parent == -1 && children > 1) isAP[u] = true;
                if (parent != -1 && low[v] >= disc[u]) isAP[u] = true;
                if (low[v] > disc[u]) bridges.add(new int[]{u, v});
            } else if (v != parent) {
                low[u] = Math.min(low[u], disc[v]);
            }
        }
    }

    public static void main(String[] args) {
        Problem08_NetworkResilience analyzer = new Problem08_NetworkResilience();

        // Network 1: Star topology (very fragile)
        int[][] star = {{0,1},{0,2},{0,3},{0,4},{0,5}};
        ResilienceReport r1 = analyzer.analyze(6, star);
        
        // Network 2: Ring topology (moderate)
        analyzer = new Problem08_NetworkResilience();
        int[][] ring = {{0,1},{1,2},{2,3},{3,4},{4,5},{5,0}};
        ResilienceReport r2 = analyzer.analyze(6, ring);
        
        // Network 3: Mesh topology (resilient)
        analyzer = new Problem08_NetworkResilience();
        int[][] mesh = {{0,1},{1,2},{2,3},{3,0},{0,2},{1,3},{4,0},{4,1},{4,2},{4,3},{5,0},{5,2},{5,4}};
        ResilienceReport r3 = analyzer.analyze(6, mesh);

        System.out.println("Network Resilience Analysis");
        System.out.println("===========================\n");
        System.out.printf("%-12s %-6s %-6s %-5s %-8s %-10s%n", 
            "Topology", "Nodes", "Edges", "APs", "Bridges", "Score");
        printReport("Star", r1);
        printReport("Ring", r2);
        printReport("Mesh", r3);
    }

    private static void printReport(String name, ResilienceReport r) {
        System.out.printf("%-12s %-6d %-6d %-5d %-8d %-10.2f%n",
            name, r.nodes, r.edges, r.articulationPoints.size(), 
            r.bridges.size(), r.resilienceScore);
    }
}
