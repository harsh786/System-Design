import java.util.*;

/**
 * Problem: Course Schedule BFS/Kahn's Algorithm (LeetCode 207)
 * Approach: Kahn's - start from nodes with in-degree 0, peel layers
 * Time: O(V+E), Space: O(V+E)
 * Production Analogy: Deployment orchestration - deploy services with zero unmet dependencies first
 */
public class Problem09_CourseScheduleKahn {
    public boolean canFinish(int numCourses, int[][] prerequisites) {
        int[] indegree = new int[numCourses];
        List<List<Integer>> graph = new ArrayList<>();
        for (int i = 0; i < numCourses; i++) graph.add(new ArrayList<>());
        for (int[] p : prerequisites) { graph.get(p[1]).add(p[0]); indegree[p[0]]++; }
        Queue<Integer> q = new LinkedList<>();
        for (int i = 0; i < numCourses; i++) if (indegree[i] == 0) q.offer(i);
        int count = 0;
        while (!q.isEmpty()) {
            int node = q.poll(); count++;
            for (int next : graph.get(node))
                if (--indegree[next] == 0) q.offer(next);
        }
        return count == numCourses;
    }

    public static void main(String[] args) {
        System.out.println(new Problem09_CourseScheduleKahn().canFinish(2, new int[][]{{1,0}})); // true
        System.out.println(new Problem09_CourseScheduleKahn().canFinish(2, new int[][]{{1,0},{0,1}})); // false
    }
}
