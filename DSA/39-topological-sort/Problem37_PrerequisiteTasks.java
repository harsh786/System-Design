import java.util.*;

/**
 * Problem: Prerequisite Tasks
 * Check if a task can be completed given available completed tasks and prerequisites.
 *
 * Approach: BFS from completed tasks, check if target becomes reachable
 *
 * Time Complexity: O(V + E)
 * Space Complexity: O(V + E)
 *
 * Production Analogy: Checking if a deployment can proceed given current system state.
 */
public class Problem37_PrerequisiteTasks {

    public boolean canComplete(int target, Set<Integer> completed, int n, int[][] prereqs) {
        List<List<Integer>> graph = new ArrayList<>();
        int[] inDeg = new int[n];
        for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
        for (int[] p : prereqs) {
            if (!completed.contains(p[1])) { // only consider non-completed prereqs
                graph.get(p[1]).add(p[0]);
                if (!completed.contains(p[0])) inDeg[p[0]]++;
            }
        }

        Queue<Integer> q = new LinkedList<>();
        for (int i = 0; i < n; i++)
            if (inDeg[i] == 0 || completed.contains(i)) q.offer(i);

        Set<Integer> reachable = new HashSet<>(completed);
        while (!q.isEmpty()) {
            int node = q.poll();
            reachable.add(node);
            for (int nei : graph.get(node))
                if (--inDeg[nei] == 0) q.offer(nei);
        }
        return reachable.contains(target);
    }

    public static void main(String[] args) {
        Problem37_PrerequisiteTasks solver = new Problem37_PrerequisiteTasks();
        Set<Integer> done = new HashSet<>(Arrays.asList(0, 1));
        System.out.println(solver.canComplete(3, done, 4, new int[][]{{2,0},{3,1},{3,2}})); // true
    }
}
