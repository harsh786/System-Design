import java.util.*;

public class Problem41_TheMaze {
    public static boolean hasPath(int[][] maze, int[] start, int[] dest) {
        int m = maze.length, n = maze[0].length;
        boolean[][] visited = new boolean[m][n];
        Queue<int[]> q = new LinkedList<>();
        q.offer(start); visited[start[0]][start[1]] = true;
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        while (!q.isEmpty()) {
            int[] c = q.poll();
            if (c[0] == dest[0] && c[1] == dest[1]) return true;
            for (int[] d : dirs) {
                int r = c[0], col = c[1];
                while (r+d[0] >= 0 && r+d[0] < m && col+d[1] >= 0 && col+d[1] < n && maze[r+d[0]][col+d[1]] == 0) { r += d[0]; col += d[1]; }
                if (!visited[r][col]) { visited[r][col] = true; q.offer(new int[]{r, col}); }
            }
        }
        return false;
    }
    public static void main(String[] args) {
        int[][] maze = {{0,0,1,0,0},{0,0,0,0,0},{0,0,0,1,0},{1,1,0,1,1},{0,0,0,0,0}};
        System.out.println(hasPath(maze, new int[]{0,4}, new int[]{4,4})); // true
    }
}
