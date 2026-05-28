import java.util.*;

/**
 * Problem: Course Schedule (LeetCode 207)
 * Approach: DFS cycle detection with 3-color marking (unvisited/in-progress/done)
 * Time: O(V+E), Space: O(V+E)
 * Production Analogy: Detecting circular dependencies in microservice deployment pipelines
 */
public class Problem03_CourseSchedule {
    public boolean canFinish(int numCourses, int[][] prerequisites) {
        List<List<Integer>> graph = new ArrayList<>();
        for (int i = 0; i < numCourses; i++) graph.add(new ArrayList<>());
        for (int[] p : prerequisites) graph.get(p[1]).add(p[0]);

        int[] color = new int[numCourses]; // 0=white, 1=gray, 2=black
        for (int i = 0; i < numCourses; i++) {
            if (color[i] == 0 && hasCycle(graph, i, color)) return false;
        }
        return true;
    }

    private boolean hasCycle(List<List<Integer>> graph, int node, int[] color) {
        color[node] = 1;
        for (int next : graph.get(node)) {
            if (color[next] == 1) return true;
            if (color[next] == 0 && hasCycle(graph, next, color)) return true;
        }
        color[node] = 2;
        return false;
    }

    public static void main(String[] args) {
        Problem03_CourseSchedule sol = new Problem03_CourseSchedule();
        System.out.println(sol.canFinish(2, new int[][]{{1,0}})); // true
        System.out.println(sol.canFinish(2, new int[][]{{1,0},{0,1}})); // false
    }
}
