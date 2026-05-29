import java.util.*;

/**
 * Problem: Course Schedule IV
 * Answer queries: is course a prerequisite of course b?
 *
 * Approach: Topological sort + transitive closure using boolean reachability matrix
 *
 * Time Complexity: O(V^2 + V*E + Q)
 * Space Complexity: O(V^2)
 *
 * Production Analogy: Pre-computing dependency reachability for fast permission checks.
 */
public class Problem19_CourseScheduleIV {

    public List<Boolean> checkIfPrerequisite(int n, int[][] prereqs, int[][] queries) {
        boolean[][] reach = new boolean[n][n];
        List<List<Integer>> graph = new ArrayList<>();
        int[] inDeg = new int[n];
        for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
        for (int[] p : prereqs) { graph.get(p[0]).add(p[1]); inDeg[p[1]]++; }

        Queue<Integer> q = new LinkedList<>();
        for (int i = 0; i < n; i++) if (inDeg[i] == 0) q.offer(i);

        while (!q.isEmpty()) {
            int node = q.poll();
            for (int nei : graph.get(node)) {
                reach[node][nei] = true;
                for (int i = 0; i < n; i++)
                    if (reach[i][node]) reach[i][nei] = true;
                if (--inDeg[nei] == 0) q.offer(nei);
            }
        }

        List<Boolean> result = new ArrayList<>();
        for (int[] query : queries) result.add(reach[query[0]][query[1]]);
        return result;
    }

    public static void main(String[] args) {
        Problem19_CourseScheduleIV solver = new Problem19_CourseScheduleIV();
        System.out.println(solver.checkIfPrerequisite(3, new int[][]{{1,2},{1,0},{2,0}}, new int[][]{{1,0},{1,2}}));
    }
}
