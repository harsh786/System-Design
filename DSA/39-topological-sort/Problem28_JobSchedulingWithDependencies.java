import java.util.*;

/**
 * Problem: Job Scheduling with Dependencies
 * Assign jobs to workers respecting dependencies, minimize makespan.
 *
 * Approach: Topological sort + greedy assignment to earliest available worker
 *
 * Time Complexity: O(V + E + V log W) where W = workers
 * Space Complexity: O(V + E)
 *
 * Production Analogy: Kubernetes job scheduling with init container dependencies.
 */
public class Problem28_JobSchedulingWithDependencies {

    public int minMakespan(int n, int[] durations, int[][] deps, int workers) {
        List<List<Integer>> graph = new ArrayList<>();
        int[] inDeg = new int[n], earliest = new int[n];
        for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
        for (int[] d : deps) { graph.get(d[0]).add(d[1]); inDeg[d[1]]++; }

        Queue<Integer> q = new LinkedList<>();
        for (int i = 0; i < n; i++) if (inDeg[i] == 0) q.offer(i);

        // Process in topological order, assign to earliest free worker
        PriorityQueue<Integer> workerFree = new PriorityQueue<>();
        for (int i = 0; i < workers; i++) workerFree.offer(0);

        int makespan = 0;
        while (!q.isEmpty()) {
            int node = q.poll();
            int start = Math.max(earliest[node], workerFree.poll());
            int end = start + durations[node];
            makespan = Math.max(makespan, end);
            workerFree.offer(end);
            for (int nei : graph.get(node)) {
                earliest[nei] = Math.max(earliest[nei], end);
                if (--inDeg[nei] == 0) q.offer(nei);
            }
        }
        return makespan;
    }

    public static void main(String[] args) {
        Problem28_JobSchedulingWithDependencies solver = new Problem28_JobSchedulingWithDependencies();
        System.out.println(solver.minMakespan(4, new int[]{2,3,1,4}, new int[][]{{0,2},{1,3}}, 2));
    }
}
