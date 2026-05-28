import java.util.*;

/**
 * Problem: Course Schedule II (LeetCode 210)
 * Approach: DFS topological sort - post-order gives reverse topo order
 * Time: O(V+E), Space: O(V+E)
 * Production Analogy: Determining build order for dependent microservices in CI/CD
 */
public class Problem04_CourseScheduleII {
    public int[] findOrder(int numCourses, int[][] prerequisites) {
        List<List<Integer>> graph = new ArrayList<>();
        for (int i = 0; i < numCourses; i++) graph.add(new ArrayList<>());
        for (int[] p : prerequisites) graph.get(p[1]).add(p[0]);

        int[] color = new int[numCourses];
        Deque<Integer> stack = new ArrayDeque<>();
        for (int i = 0; i < numCourses; i++) {
            if (color[i] == 0 && !dfs(graph, i, color, stack)) return new int[0];
        }
        int[] result = new int[numCourses];
        for (int i = 0; i < numCourses; i++) result[i] = stack.pop();
        return result;
    }

    private boolean dfs(List<List<Integer>> graph, int node, int[] color, Deque<Integer> stack) {
        color[node] = 1;
        for (int next : graph.get(node)) {
            if (color[next] == 1) return false;
            if (color[next] == 0 && !dfs(graph, next, color, stack)) return false;
        }
        color[node] = 2;
        stack.push(node);
        return true;
    }

    public static void main(String[] args) {
        Problem04_CourseScheduleII sol = new Problem04_CourseScheduleII();
        System.out.println(Arrays.toString(sol.findOrder(4, new int[][]{{1,0},{2,0},{3,1},{3,2}})));
    }
}
