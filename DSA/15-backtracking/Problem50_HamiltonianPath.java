import java.util.*;

/**
 * Problem 50: Hamiltonian Path
 * 
 * Determine if a Hamiltonian path exists in a graph (visits every vertex exactly once).
 * 
 * Search Tree:
 * - Try starting from each vertex
 * - At each vertex, try all unvisited neighbors
 * - Path is valid when all vertices are visited
 * 
 * Pruning Strategy:
 * - If remaining unvisited vertices are disconnected from current, prune
 * - Use bitmask for visited state (efficient for small graphs)
 * - Can add DP memoization: dp[mask][last_vertex]
 * 
 * Time Complexity: O(n! ) naive, O(2^n * n^2) with DP+bitmask
 * Space Complexity: O(2^n * n) with DP
 * 
 * Production Analogy:
 * - TSP variant: visiting all data centers in a network exactly once for maintenance.
 */
public class Problem50_HamiltonianPath {

    // Backtracking approach
    public boolean hasHamiltonianPath(int n, int[][] edges) {
        List<List<Integer>> adj = new ArrayList<>();
        for (int i = 0; i < n; i++) adj.add(new ArrayList<>());
        for (int[] e : edges) { adj.get(e[0]).add(e[1]); adj.get(e[1]).add(e[0]); }

        boolean[] visited = new boolean[n];
        for (int start = 0; start < n; start++) {
            visited[start] = true;
            if (dfs(adj, visited, start, 1, n)) return true;
            visited[start] = false;
        }
        return false;
    }

    private boolean dfs(List<List<Integer>> adj, boolean[] visited, int curr, int count, int n) {
        if (count == n) return true;
        for (int next : adj.get(curr)) {
            if (visited[next]) continue;
            visited[next] = true;
            if (dfs(adj, visited, next, count + 1, n)) return true;
            visited[next] = false;
        }
        return false;
    }

    // DP + Bitmask approach (more efficient)
    public boolean hasHamiltonianPathDP(int n, int[][] edges) {
        List<List<Integer>> adj = new ArrayList<>();
        for (int i = 0; i < n; i++) adj.add(new ArrayList<>());
        for (int[] e : edges) { adj.get(e[0]).add(e[1]); adj.get(e[1]).add(e[0]); }

        // dp[mask][i] = can we visit exactly the vertices in mask, ending at i?
        boolean[][] dp = new boolean[1 << n][n];
        for (int i = 0; i < n; i++) dp[1 << i][i] = true;

        for (int mask = 1; mask < (1 << n); mask++) {
            for (int u = 0; u < n; u++) {
                if (!dp[mask][u]) continue;
                if ((mask & (1 << u)) == 0) continue;
                for (int v : adj.get(u)) {
                    if ((mask & (1 << v)) != 0) continue;
                    dp[mask | (1 << v)][v] = true;
                }
            }
        }

        int fullMask = (1 << n) - 1;
        for (int i = 0; i < n; i++)
            if (dp[fullMask][i]) return true;
        return false;
    }

    public static void main(String[] args) {
        Problem50_HamiltonianPath sol = new Problem50_HamiltonianPath();

        // Complete graph K4 - definitely has Hamiltonian path
        System.out.println(sol.hasHamiltonianPath(4,
            new int[][]{{0,1},{0,2},{0,3},{1,2},{1,3},{2,3}})); // true

        // Path graph 0-1-2-3
        System.out.println(sol.hasHamiltonianPath(4,
            new int[][]{{0,1},{1,2},{2,3}})); // true

        // Disconnected graph
        System.out.println(sol.hasHamiltonianPath(4,
            new int[][]{{0,1},{2,3}})); // false

        // DP approach
        System.out.println(sol.hasHamiltonianPathDP(4,
            new int[][]{{0,1},{0,2},{0,3},{1,2},{1,3},{2,3}})); // true

        System.out.println(sol.hasHamiltonianPathDP(4,
            new int[][]{{0,1},{2,3}})); // false

        // Star graph (center 0 connected to all) - no Hamiltonian path for n>3 without other edges
        System.out.println(sol.hasHamiltonianPath(5,
            new int[][]{{0,1},{0,2},{0,3},{0,4}})); // false
    }
}
