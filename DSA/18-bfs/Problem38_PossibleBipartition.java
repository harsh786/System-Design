import java.util.*;

/**
 * Problem: Possible Bipartition (LeetCode 886)
 * Approach: BFS 2-coloring on dislike graph
 * Time: O(V+E), Space: O(V+E)
 * Production Analogy: Splitting services into two non-conflicting deployment groups
 */
public class Problem38_PossibleBipartition {
    public boolean possibleBipartition(int n, int[][] dislikes) {
        List<List<Integer>> graph = new ArrayList<>();
        for (int i = 0; i <= n; i++) graph.add(new ArrayList<>());
        for (int[] d : dislikes) { graph.get(d[0]).add(d[1]); graph.get(d[1]).add(d[0]); }
        int[] color = new int[n + 1];
        for (int i = 1; i <= n; i++) {
            if (color[i] != 0) continue;
            Queue<Integer> q = new LinkedList<>();
            q.offer(i); color[i] = 1;
            while (!q.isEmpty()) {
                int node = q.poll();
                for (int next : graph.get(node)) {
                    if (color[next] == 0) { color[next] = -color[node]; q.offer(next); }
                    else if (color[next] == color[node]) return false;
                }
            }
        }
        return true;
    }

    public static void main(String[] args) {
        System.out.println(new Problem38_PossibleBipartition().possibleBipartition(4, new int[][]{{1,2},{1,3},{2,4}})); // true
    }
}
