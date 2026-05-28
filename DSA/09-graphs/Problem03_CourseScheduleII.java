import java.util.*;

/**
 * Problem 3: Course Schedule II (LeetCode 210)
 * 
 * Approach: Topological sort returning the order. Same as Course Schedule but collect results.
 * Time: O(V + E), Space: O(V + E)
 * 
 * Production Analogy: Determining deployment order for microservices with dependencies.
 */
public class Problem03_CourseScheduleII {
    
    public int[] findOrder(int numCourses, int[][] prerequisites) {
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
        int[] result = new int[numCourses];
        int idx = 0;
        while (!queue.isEmpty()) {
            int curr = queue.poll();
            result[idx++] = curr;
            for (int next : adj.get(curr))
                if (--indegree[next] == 0) queue.offer(next);
        }
        return idx == numCourses ? result : new int[0];
    }
    
    public static void main(String[] args) {
        Problem03_CourseScheduleII sol = new Problem03_CourseScheduleII();
        System.out.println(Arrays.toString(sol.findOrder(4, new int[][]{{1,0},{2,0},{3,1},{3,2}}))); 
        System.out.println(Arrays.toString(sol.findOrder(2, new int[][]{{1,0},{0,1}}))); // [] (cycle)
        System.out.println(Arrays.toString(sol.findOrder(1, new int[][]{}))); // [0]
    }
}
