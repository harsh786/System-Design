import java.util.*;

/**
 * Problem 32: The Maze
 * 
 * Ball rolls in a direction until hitting a wall. Determine if it can reach destination.
 *
 * Approach: BFS/DFS where each move rolls the ball until it hits a wall.
 *
 * Time Complexity: O(m * n * max(m,n))
 * Space Complexity: O(m * n)
 *
 * Production Analogy: Packet routing in a network where packets travel through a
 * pipeline until reaching a switch (wall) - modeling network segment traversal.
 */
public class Problem32_TheMaze {

    public static boolean hasPath(int[][] maze, int[] start, int[] destination) {
        int m = maze.length, n = maze[0].length;
        boolean[][] visited = new boolean[m][n];
        Queue<int[]> queue = new LinkedList<>();
        queue.offer(start);
        visited[start[0]][start[1]] = true;
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        while (!queue.isEmpty()) {
            int[] cur = queue.poll();
            if (cur[0] == destination[0] && cur[1] == destination[1]) return true;
            for (int[] d : dirs) {
                int ni = cur[0], nj = cur[1];
                while (ni+d[0] >= 0 && ni+d[0] < m && nj+d[1] >= 0 && nj+d[1] < n && maze[ni+d[0]][nj+d[1]] == 0) {
                    ni += d[0]; nj += d[1];
                }
                if (!visited[ni][nj]) {
                    visited[ni][nj] = true;
                    queue.offer(new int[]{ni, nj});
                }
            }
        }
        return false;
    }

    public static void main(String[] args) {
        int[][] maze = {{0,0,1,0,0},{0,0,0,0,0},{0,0,0,1,0},{1,1,0,1,1},{0,0,0,0,0}};
        System.out.println("Test 1: " + hasPath(maze, new int[]{0,4}, new int[]{4,4})); // true
        System.out.println("Test 2: " + hasPath(maze, new int[]{0,4}, new int[]{3,2})); // false
    }
}
