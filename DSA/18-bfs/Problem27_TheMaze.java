import java.util.*;

/**
 * Problem: The Maze (LeetCode 490)
 * Approach: BFS where ball rolls until hitting wall (not single step)
 * Time: O(M*N), Space: O(M*N)
 * Production Analogy: Packet routing where messages travel until hitting a boundary/router
 */
public class Problem27_TheMaze {
    public boolean hasPath(int[][] maze, int[] start, int[] destination) {
        int m = maze.length, n = maze[0].length;
        boolean[][] visited = new boolean[m][n];
        Queue<int[]> q = new LinkedList<>();
        q.offer(start); visited[start[0]][start[1]] = true;
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        while (!q.isEmpty()) {
            int[] curr = q.poll();
            if (curr[0] == destination[0] && curr[1] == destination[1]) return true;
            for (int[] d : dirs) {
                int r = curr[0], c = curr[1];
                while (r+d[0] >= 0 && r+d[0] < m && c+d[1] >= 0 && c+d[1] < n && maze[r+d[0]][c+d[1]] == 0) {
                    r += d[0]; c += d[1];
                }
                if (!visited[r][c]) { visited[r][c] = true; q.offer(new int[]{r, c}); }
            }
        }
        return false;
    }

    public static void main(String[] args) {
        int[][] maze = {{0,0,1,0,0},{0,0,0,0,0},{0,0,0,1,0},{1,1,0,1,1},{0,0,0,0,0}};
        System.out.println(new Problem27_TheMaze().hasPath(maze, new int[]{0,4}, new int[]{4,4})); // true
    }
}
