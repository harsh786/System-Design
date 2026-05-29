import java.util.*;

/**
 * Problem: Parallel Courses III
 * Minimum time to complete all courses with given time per course.
 *
 * Approach: Topological sort + DP tracking max completion time
 *
 * Time Complexity: O(V + E)
 * Space Complexity: O(V + E)
 *
 * Production Analogy: Computing total pipeline execution time with parallel stages.
 */
public class Problem36_ParallelCoursesIII {

    public int minimumTime(int n, int[][] relations, int[] time) {
        List<List<Integer>> graph = new ArrayList<>();
        int[] inDeg = new int[n + 1], dist = new int[n + 1];
        for (int i = 0; i <= n; i++) graph.add(new ArrayList<>());
        for (int[] r : relations) { graph.get(r[0]).add(r[1]); inDeg[r[1]]++; }

        Queue<Integer> q = new LinkedList<>();
        for (int i = 1; i <= n; i++) { dist[i] = time[i-1]; if (inDeg[i] == 0) q.offer(i); }

        int ans = 0;
        while (!q.isEmpty()) {
            int node = q.poll();
            ans = Math.max(ans, dist[node]);
            for (int nei : graph.get(node)) {
                dist[nei] = Math.max(dist[nei], dist[node] + time[nei-1]);
                if (--inDeg[nei] == 0) q.offer(nei);
            }
        }
        return ans;
    }

    public static void main(String[] args) {
        Problem36_ParallelCoursesIII solver = new Problem36_ParallelCoursesIII();
        System.out.println(solver.minimumTime(3, new int[][]{{1,3},{2,3}}, new int[]{3,2,5})); // 8
    }
}
