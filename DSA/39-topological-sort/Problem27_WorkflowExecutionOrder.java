import java.util.*;

/**
 * Problem: Workflow Execution Order
 * Given workflow steps with dependencies, find valid execution order with parallelism levels.
 *
 * Approach: BFS topological sort returning levels (parallel batches)
 *
 * Time Complexity: O(V + E)
 * Space Complexity: O(V + E)
 *
 * Production Analogy: Orchestrating Airflow DAG tasks in parallel stages.
 */
public class Problem27_WorkflowExecutionOrder {

    public List<List<Integer>> executionBatches(int n, int[][] deps) {
        List<List<Integer>> graph = new ArrayList<>(), batches = new ArrayList<>();
        int[] inDeg = new int[n];
        for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
        for (int[] d : deps) { graph.get(d[0]).add(d[1]); inDeg[d[1]]++; }

        Queue<Integer> q = new LinkedList<>();
        for (int i = 0; i < n; i++) if (inDeg[i] == 0) q.offer(i);

        while (!q.isEmpty()) {
            List<Integer> batch = new ArrayList<>();
            int size = q.size();
            for (int i = 0; i < size; i++) {
                int node = q.poll(); batch.add(node);
                for (int nei : graph.get(node)) if (--inDeg[nei] == 0) q.offer(nei);
            }
            batches.add(batch);
        }
        return batches;
    }

    public static void main(String[] args) {
        Problem27_WorkflowExecutionOrder solver = new Problem27_WorkflowExecutionOrder();
        System.out.println(solver.executionBatches(5, new int[][]{{0,2},{1,2},{2,3},{2,4}}));
    }
}
