import java.util.*;

/**
 * Problem: Nearest Exit from Entrance in Maze
 *
 * Approach: BFS from entrance, find nearest border cell
 *
 * Time Complexity: O(m*n)
 * Space Complexity: O(m*n)
 *
 * Production Analogy: Finding nearest egress point in a network for traffic offloading.
 */
public class Problem29_NearestExitFromEntranceInMaze {

    public int nearestExit(char[][] maze, int[] entrance) {
        int m = maze.length, n = maze[0].length;
        Queue<int[]> q = new LinkedList<>();
        q.offer(new int[]{entrance[0], entrance[1], 0});
        maze[entrance[0]][entrance[1]] = '+';
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};

        while (!q.isEmpty()) {
            int[] cur = q.poll();
            for (int[] d : dirs) {
                int nr = cur[0]+d[0], nc = cur[1]+d[1];
                if (nr>=0&&nr<m&&nc>=0&&nc<n&&maze[nr][nc]=='.') {
                    if (nr==0||nr==m-1||nc==0||nc==n-1) return cur[2]+1;
                    maze[nr][nc] = '+'; q.offer(new int[]{nr, nc, cur[2]+1});
                }
            }
        }
        return -1;
    }

    public static void main(String[] args) {
        Problem29_NearestExitFromEntranceInMaze solver = new Problem29_NearestExitFromEntranceInMaze();
        char[][] maze = {{'+','+','.','+'},{'.','.','.','+'},{'+','+','+','.'}};
        System.out.println(solver.nearestExit(maze, new int[]{1, 2})); // 1
    }
}
