import java.util.*;

/**
 * Problem: Largest Color Value in a Directed Graph
 *
 * Approach: Topological sort + DP tracking max count of each color on paths
 *
 * Time Complexity: O((V + E) * 26)
 * Space Complexity: O(V * 26)
 *
 * Production Analogy: Finding the most common label along any execution path in a workflow.
 */
public class Problem23_LargestColorValueInDirectedGraph {

    public int largestPathValue(String colors, int[][] edges) {
        int n = colors.length();
        List<List<Integer>> graph = new ArrayList<>();
        int[] inDeg = new int[n];
        for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
        for (int[] e : edges) { graph.get(e[0]).add(e[1]); inDeg[e[1]]++; }

        int[][] dp = new int[n][26];
        Queue<Integer> q = new LinkedList<>();
        for (int i = 0; i < n; i++) {
            if (inDeg[i] == 0) q.offer(i);
            dp[i][colors.charAt(i) - 'a'] = 1;
        }

        int count = 0, result = 0;
        while (!q.isEmpty()) {
            int node = q.poll(); count++;
            for (int c = 0; c < 26; c++) result = Math.max(result, dp[node][c]);
            for (int nei : graph.get(node)) {
                for (int c = 0; c < 26; c++)
                    dp[nei][c] = Math.max(dp[nei][c], dp[node][c] + (colors.charAt(nei)-'a'==c ? 1 : 0));
                if (--inDeg[nei] == 0) q.offer(nei);
            }
        }
        return count == n ? result : -1;
    }

    public static void main(String[] args) {
        Problem23_LargestColorValueInDirectedGraph solver = new Problem23_LargestColorValueInDirectedGraph();
        System.out.println(solver.largestPathValue("abaca", new int[][]{{0,1},{0,2},{2,3},{3,4}})); // 3
    }
}
