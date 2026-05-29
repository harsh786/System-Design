import java.util.*;

/**
 * Problem: Course Schedule II
 * Return the ordering of courses you should take to finish all courses.
 *
 * Approach: Kahn's Algorithm - BFS topological sort collecting order
 *
 * Time Complexity: O(V + E)
 * Space Complexity: O(V + E)
 *
 * Production Analogy: Determining the order to deploy microservices based on dependencies.
 */
public class Problem02_CourseScheduleII {

    public int[] findOrder(int numCourses, int[][] prerequisites) {
        List<List<Integer>> graph = new ArrayList<>();
        int[] inDegree = new int[numCourses];

        for (int i = 0; i < numCourses; i++) graph.add(new ArrayList<>());
        for (int[] pre : prerequisites) {
            graph.get(pre[1]).add(pre[0]);
            inDegree[pre[0]]++;
        }

        Queue<Integer> queue = new LinkedList<>();
        for (int i = 0; i < numCourses; i++)
            if (inDegree[i] == 0) queue.offer(i);

        int[] order = new int[numCourses];
        int idx = 0;
        while (!queue.isEmpty()) {
            int node = queue.poll();
            order[idx++] = node;
            for (int nei : graph.get(node))
                if (--inDegree[nei] == 0) queue.offer(nei);
        }
        return idx == numCourses ? order : new int[0];
    }

    public static void main(String[] args) {
        Problem02_CourseScheduleII solver = new Problem02_CourseScheduleII();
        System.out.println(Arrays.toString(solver.findOrder(4, new int[][]{{1,0},{2,0},{3,1},{3,2}})));
    }
}
