import java.util.*;

/**
 * Problem: As Far from Land as Possible
 * Find water cell with maximum distance to nearest land.
 *
 * Approach: Multi-source BFS from all land cells simultaneously
 *
 * Time Complexity: O(m*n)
 * Space Complexity: O(m*n)
 *
 * Production Analogy: Finding the point in a network furthest from any server.
 */
public class Problem28_AsFarFromLandAsPossible {

    public int maxDistance(int[][] grid) {
        int n = grid.length;
        Queue<int[]> q = new LinkedList<>();
        for (int i = 0; i < n; i++)
            for (int j = 0; j < n; j++)
                if (grid[i][j] == 1) q.offer(new int[]{i, j});

        if (q.size() == 0 || q.size() == n * n) return -1;
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        int dist = -1;
        while (!q.isEmpty()) {
            int size = q.size(); dist++;
            for (int i = 0; i < size; i++) {
                int[] cur = q.poll();
                for (int[] d : dirs) {
                    int nr = cur[0]+d[0], nc = cur[1]+d[1];
                    if (nr>=0&&nr<n&&nc>=0&&nc<n&&grid[nr][nc]==0) {
                        grid[nr][nc] = 1; q.offer(new int[]{nr, nc});
                    }
                }
            }
        }
        return dist;
    }

    public static void main(String[] args) {
        Problem28_AsFarFromLandAsPossible solver = new Problem28_AsFarFromLandAsPossible();
        System.out.println(solver.maxDistance(new int[][]{{1,0,1},{0,0,0},{1,0,1}})); // 2
    }
}
