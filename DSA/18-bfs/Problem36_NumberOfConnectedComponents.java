import java.util.*;

/**
 * Problem: Number of Connected Components (LeetCode 323)
 * Approach: BFS from each unvisited node counting components
 * Time: O(V+E), Space: O(V+E)
 * Production Analogy: Counting isolated network segments for split-brain detection
 */
public class Problem36_NumberOfConnectedComponents {
    public int countComponents(int n, int[][] edges) {
        List<List<Integer>> graph = new ArrayList<>();
        for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
        for (int[] e : edges) { graph.get(e[0]).add(e[1]); graph.get(e[1]).add(e[0]); }
        boolean[] visited = new boolean[n];
        int count = 0;
        for (int i = 0; i < n; i++) {
            if (!visited[i]) {
                count++;
                Queue<Integer> q = new LinkedList<>();
                q.offer(i); visited[i] = true;
                while (!q.isEmpty()) {
                    int node = q.poll();
                    for (int next : graph.get(node))
                        if (!visited[next]) { visited[next] = true; q.offer(next); }
                }
            }
        }
        return count;
    }

    public static void main(String[] args) {
        System.out.println(new Problem36_NumberOfConnectedComponents().countComponents(5, new int[][]{{0,1},{1,2},{3,4}})); // 2
    }
}
