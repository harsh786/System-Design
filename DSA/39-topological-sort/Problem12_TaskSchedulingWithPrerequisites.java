import java.util.*;

/**
 * Problem: Task Scheduling with Prerequisites
 * Schedule tasks with durations and prerequisites, find minimum completion time.
 *
 * Approach: Topological sort + DP for earliest start time (critical path)
 *
 * Time Complexity: O(V + E)
 * Space Complexity: O(V + E)
 *
 * Production Analogy: CI/CD pipeline scheduling with dependent stages and parallelism.
 */
public class Problem12_TaskSchedulingWithPrerequisites {

    public int minCompletionTime(int n, int[] durations, int[][] prereqs) {
        List<List<Integer>> graph = new ArrayList<>();
        int[] inDeg = new int[n];
        for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
        for (int[] p : prereqs) { graph.get(p[0]).add(p[1]); inDeg[p[1]]++; }

        int[] earliest = new int[n];
        Queue<Integer> q = new LinkedList<>();
        for (int i = 0; i < n; i++) if (inDeg[i] == 0) q.offer(i);

        int maxTime = 0;
        while (!q.isEmpty()) {
            int node = q.poll();
            int finish = earliest[node] + durations[node];
            maxTime = Math.max(maxTime, finish);
            for (int nei : graph.get(node)) {
                earliest[nei] = Math.max(earliest[nei], finish);
                if (--inDeg[nei] == 0) q.offer(nei);
            }
        }
        return maxTime;
    }

    public static void main(String[] args) {
        Problem12_TaskSchedulingWithPrerequisites solver = new Problem12_TaskSchedulingWithPrerequisites();
        System.out.println(solver.minCompletionTime(4, new int[]{3,2,1,4}, new int[][]{{0,1},{0,2},{1,3},{2,3}})); // 9
    }
}
