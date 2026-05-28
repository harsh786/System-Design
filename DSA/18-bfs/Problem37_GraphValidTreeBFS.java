import java.util.*;

/**
 * Problem: Graph Valid Tree BFS (LeetCode 261)
 * Approach: BFS - valid tree = n-1 edges + all nodes reachable from node 0
 * Time: O(V+E), Space: O(V+E)
 * Production Analogy: Verifying service hierarchy is a proper tree (no loops, fully connected)
 */
public class Problem37_GraphValidTreeBFS {
    public boolean validTree(int n, int[][] edges) {
        if (edges.length != n - 1) return false;
        List<List<Integer>> graph = new ArrayList<>();
        for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
        for (int[] e : edges) { graph.get(e[0]).add(e[1]); graph.get(e[1]).add(e[0]); }
        boolean[] visited = new boolean[n];
        Queue<Integer> q = new LinkedList<>();
        q.offer(0); visited[0] = true;
        int count = 0;
        while (!q.isEmpty()) {
            int node = q.poll(); count++;
            for (int next : graph.get(node))
                if (!visited[next]) { visited[next] = true; q.offer(next); }
        }
        return count == n;
    }

    public static void main(String[] args) {
        System.out.println(new Problem37_GraphValidTreeBFS().validTree(5, new int[][]{{0,1},{0,2},{0,3},{1,4}})); // true
    }
}
