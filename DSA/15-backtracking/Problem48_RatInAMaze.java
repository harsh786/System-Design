import java.util.*;

/**
 * Problem 48: Rat in a Maze
 * 
 * Find all paths from (0,0) to (n-1,n-1) in a binary matrix (1=open, 0=blocked).
 * Can move in 4 directions: D(down), L(left), R(right), U(up).
 * 
 * Search Tree:
 * - From current cell, try D, L, R, U (alphabetical order for sorted output)
 * - Mark visited to avoid cycles
 * 
 * Pruning Strategy:
 * - Skip blocked cells (0) and visited cells
 * - If start or end is blocked, return immediately
 * 
 * Time Complexity: O(4^(n^2)) worst case
 * Space Complexity: O(n^2) for visited + path
 * 
 * Production Analogy:
 * - Network routing: finding all possible paths from source to destination in a topology.
 */
public class Problem48_RatInAMaze {

    private static final int[] dr = {1, 0, 0, -1}; // D, L, R, U
    private static final int[] dc = {0, -1, 1, 0};
    private static final char[] dir = {'D', 'L', 'R', 'U'};

    public List<String> findPath(int[][] maze) {
        List<String> result = new ArrayList<>();
        int n = maze.length;
        if (maze[0][0] == 0 || maze[n-1][n-1] == 0) return result;
        boolean[][] visited = new boolean[n][n];
        visited[0][0] = true;
        backtrack(maze, 0, 0, n, visited, new StringBuilder(), result);
        return result;
    }

    private void backtrack(int[][] maze, int r, int c, int n, boolean[][] visited, StringBuilder path, List<String> result) {
        if (r == n - 1 && c == n - 1) {
            result.add(path.toString());
            return;
        }
        for (int i = 0; i < 4; i++) {
            int nr = r + dr[i], nc = c + dc[i];
            if (nr >= 0 && nr < n && nc >= 0 && nc < n && !visited[nr][nc] && maze[nr][nc] == 1) {
                visited[nr][nc] = true;
                path.append(dir[i]);
                backtrack(maze, nr, nc, n, visited, path, result);
                path.deleteCharAt(path.length() - 1);
                visited[nr][nc] = false;
            }
        }
    }

    public static void main(String[] args) {
        Problem48_RatInAMaze sol = new Problem48_RatInAMaze();

        int[][] maze1 = {{1,0,0,0},{1,1,0,1},{1,1,0,0},{0,1,1,1}};
        System.out.println(sol.findPath(maze1)); // [DDRDRR, DRDDRR]

        int[][] maze2 = {{1,0},{1,1}};
        System.out.println(sol.findPath(maze2)); // [DR]

        int[][] maze3 = {{0,1},{1,1}};
        System.out.println(sol.findPath(maze3)); // [] (start blocked)
    }
}
