import java.util.*;

/**
 * Problem: Course Schedule
 * Determine if you can finish all courses given prerequisites.
 *
 * Approach: BFS (Kahn's Algorithm) - detect cycle in directed graph
 * - Build adjacency list and in-degree array
 * - Start with nodes having 0 in-degree
 * - If all nodes processed, no cycle exists
 *
 * Time Complexity: O(V + E)
 * Space Complexity: O(V + E)
 *
 * Production Analogy: Validating a build dependency graph has no circular dependencies
 * before starting compilation.
 */
public class Problem01_CourseSchedule {

    public boolean canFinish(int numCourses, int[][] prerequisites) {
        List<List<Integer>> graph = new ArrayList<>();
        int[] inDegree = new int[numCourses];

        for (int i = 0; i < numCourses; i++) graph.add(new ArrayList<>());

        for (int[] pre : prerequisites) {
            graph.get(pre[1]).add(pre[0]);
            inDegree[pre[0]]++;
        }

        Queue<Integer> queue = new LinkedList<>();
        for (int i = 0; i < numCourses; i++) {
            if (inDegree[i] == 0) queue.offer(i);
        }

        int count = 0;
        while (!queue.isEmpty()) {
            int node = queue.poll();
            count++;
            for (int neighbor : graph.get(node)) {
                if (--inDegree[neighbor] == 0) queue.offer(neighbor);
            }
        }

        return count == numCourses;
    }

    public static void main(String[] args) {
        Problem01_CourseSchedule solver = new Problem01_CourseSchedule();
        System.out.println(solver.canFinish(2, new int[][]{{1, 0}})); // true
        System.out.println(solver.canFinish(2, new int[][]{{1, 0}, {0, 1}})); // false
    }
}
