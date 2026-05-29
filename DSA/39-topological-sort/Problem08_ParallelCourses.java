import java.util.*;

/**
 * Problem: Parallel Courses
 * Find minimum semesters to take all courses (take all available each semester).
 *
 * Approach: BFS topological sort counting levels
 *
 * Time Complexity: O(V + E)
 * Space Complexity: O(V + E)
 *
 * Production Analogy: Determining minimum deployment waves for dependent services.
 */
public class Problem08_ParallelCourses {

    public int minimumSemesters(int n, int[][] relations) {
        List<List<Integer>> graph = new ArrayList<>();
        int[] inDeg = new int[n + 1];
        for (int i = 0; i <= n; i++) graph.add(new ArrayList<>());
        for (int[] r : relations) { graph.get(r[0]).add(r[1]); inDeg[r[1]]++; }

        Queue<Integer> q = new LinkedList<>();
        for (int i = 1; i <= n; i++) if (inDeg[i] == 0) q.offer(i);

        int semesters = 0, count = 0;
        while (!q.isEmpty()) {
            semesters++;
            int size = q.size();
            for (int i = 0; i < size; i++) {
                int node = q.poll(); count++;
                for (int nei : graph.get(node)) if (--inDeg[nei] == 0) q.offer(nei);
            }
        }
        return count == n ? semesters : -1;
    }

    public static void main(String[] args) {
        Problem08_ParallelCourses solver = new Problem08_ParallelCourses();
        System.out.println(solver.minimumSemesters(3, new int[][]{{1,3},{2,3}})); // 2
    }
}
