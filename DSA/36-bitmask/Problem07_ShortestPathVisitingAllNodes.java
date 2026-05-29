import java.util.*;

public class Problem07_ShortestPathVisitingAllNodes {
    public int shortestPathLength(int[][] graph) {
        int n = graph.length, full = (1 << n) - 1;
        boolean[][] visited = new boolean[n][1 << n];
        Queue<int[]> queue = new LinkedList<>();
        for (int i = 0; i < n; i++) { queue.offer(new int[]{i, 1 << i, 0}); visited[i][1 << i] = true; }
        while (!queue.isEmpty()) {
            int[] curr = queue.poll();
            if (curr[1] == full) return curr[2];
            for (int next : graph[curr[0]]) {
                int nextMask = curr[1] | (1 << next);
                if (!visited[next][nextMask]) { visited[next][nextMask] = true; queue.offer(new int[]{next, nextMask, curr[2] + 1}); }
            }
        }
        return -1;
    }

    public static void main(String[] args) {
        System.out.println(new Problem07_ShortestPathVisitingAllNodes().shortestPathLength(new int[][]{{1,2,3},{0},{0},{0}}));
    }
}
