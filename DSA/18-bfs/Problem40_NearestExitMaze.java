import java.util.*;

/**
 * Problem: Nearest Exit from Entrance in Maze (LeetCode 1926)
 * Approach: BFS from entrance, find first border empty cell
 * Time: O(M*N), Space: O(M*N)
 * Production Analogy: Finding nearest egress point in network topology from entry point
 */
public class Problem40_NearestExitMaze {
    public int nearestExit(char[][] maze, int[] entrance) {
        int m = maze.length, n = maze[0].length;
        Queue<int[]> q = new LinkedList<>();
        q.offer(entrance); maze[entrance[0]][entrance[1]] = '+';
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        int steps = 0;
        while (!q.isEmpty()) {
            int size = q.size(); steps++;
            for (int i = 0; i < size; i++) {
                int[] cell = q.poll();
                for (int[] d : dirs) {
                    int ni = cell[0]+d[0], nj = cell[1]+d[1];
                    if (ni >= 0 && ni < m && nj >= 0 && nj < n && maze[ni][nj] == '.') {
                        if (ni == 0 || ni == m-1 || nj == 0 || nj == n-1) return steps;
                        maze[ni][nj] = '+'; q.offer(new int[]{ni, nj});
                    }
                }
            }
        }
        return -1;
    }

    public static void main(String[] args) {
        char[][] maze = {{'+','+','.','+'},{'.','.','.','+'},{'+','+','+','.'}};
        System.out.println(new Problem40_NearestExitMaze().nearestExit(maze, new int[]{1, 2})); // 1
    }
}
