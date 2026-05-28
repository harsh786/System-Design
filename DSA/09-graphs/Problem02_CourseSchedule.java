import java.util.*;

/**
 * Problem 2: Course Schedule (LeetCode 207)
 * 
 * Approach: Detect cycle in directed graph using topological sort (Kahn's algorithm).
 * Time: O(V + E), Space: O(V + E)
 * 
 * Production Analogy: Detecting circular dependencies in build systems (Maven/Gradle).
 * If a cycle exists, the build cannot complete.
 */
public class Problem02_CourseSchedule {
    
    public boolean canFinish(int numCourses, int[][] prerequisites) {
        int[] indegree = new int[numCourses];
        List<List<Integer>> adj = new ArrayList<>();
        for (int i = 0; i < numCourses; i++) adj.add(new ArrayList<>());
        for (int[] p : prerequisites) {
            adj.get(p[1]).add(p[0]);
            indegree[p[0]]++;
        }
        Queue<Integer> queue = new LinkedList<>();
        for (int i = 0; i < numCourses; i++)
            if (indegree[i] == 0) queue.offer(i);
        int count = 0;
        while (!queue.isEmpty()) {
            int curr = queue.poll();
            count++;
            for (int next : adj.get(curr))
                if (--indegree[next] == 0) queue.offer(next);
        }
        return count == numCourses;
    }
    
    public static void main(String[] args) {
        Problem02_CourseSchedule sol = new Problem02_CourseSchedule();
        System.out.println(sol.canFinish(2, new int[][]{{1,0}})); // true
        System.out.println(sol.canFinish(2, new int[][]{{1,0},{0,1}})); // false (cycle)
        System.out.println(sol.canFinish(1, new int[][]{})); // true
        System.out.println(sol.canFinish(4, new int[][]{{1,0},{2,1},{3,2}})); // true (chain)
    }
}
