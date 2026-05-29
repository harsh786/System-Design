import java.util.*;

public class Problem13_SnakesAndLadders {
    public static int snakesAndLadders(int[][] board) {
        int n = board.length;
        boolean[] visited = new boolean[n*n+1];
        Queue<int[]> q = new LinkedList<>();
        q.offer(new int[]{1,0}); visited[1] = true;
        while (!q.isEmpty()) {
            int[] c = q.poll();
            for (int i = 1; i <= 6; i++) {
                int next = c[0] + i;
                if (next > n*n) break;
                int r = (next-1)/n, col = (next-1)%n;
                int row = n-1-r;
                int realCol = r % 2 == 0 ? col : n-1-col;
                if (board[row][realCol] != -1) next = board[row][realCol];
                if (next == n*n) return c[1]+1;
                if (!visited[next]) { visited[next] = true; q.offer(new int[]{next, c[1]+1}); }
            }
        }
        return -1;
    }
    public static void main(String[] args) {
        int[][] board = {{-1,-1,-1,-1,-1,-1},{-1,-1,-1,-1,-1,-1},{-1,-1,-1,-1,-1,-1},{-1,35,-1,-1,13,-1},{-1,-1,-1,-1,-1,-1},{-1,15,-1,-1,-1,-1}};
        System.out.println(snakesAndLadders(board)); // 4
    }
}
