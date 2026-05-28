import java.util.*;

/**
 * Problem 42: Parallel Courses (LeetCode 1136)
 * 
 * Approach: Topological sort BFS level-by-level. Number of levels = minimum semesters.
 * Time: O(V + E), Space: O(V + E)
 * 
 * Production Analogy: Minimum deployment waves when services have dependency ordering.
 */
public class Problem42_ParallelCourses {
    
    public int minimumSemesters(int n, int[][] relations) {
        int[] indegree = new int[n + 1];
        List<Integer>[] adj = new List[n + 1];
        for (int i = 0; i <= n; i++) adj[i] = new ArrayList<>();
        for (int[] r : relations) { adj[r[0]].add(r[1]); indegree[r[1]]++; }
        Queue<Integer> q = new LinkedList<>();
        for (int i = 1; i <= n; i++) if (indegree[i] == 0) q.offer(i);
        int semesters = 0, taken = 0;
        while (!q.isEmpty()) {
            semesters++;
            int size = q.size();
            for (int i = 0; i < size; i++) {
                int node = q.poll(); taken++;
                for (int next : adj[node]) if (--indegree[next] == 0) q.offer(next);
            }
        }
        return taken == n ? semesters : -1;
    }
    
    public static void main(String[] args) {
        Problem42_ParallelCourses sol = new Problem42_ParallelCourses();
        System.out.println(sol.minimumSemesters(3, new int[][]{{1,3},{2,3}})); // 2
        System.out.println(sol.minimumSemesters(3, new int[][]{{1,2},{2,3},{3,1}})); // -1
    }
}
