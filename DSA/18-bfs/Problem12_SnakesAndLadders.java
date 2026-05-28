import java.util.*;

/**
 * Problem: Snakes and Ladders (LeetCode 909)
 * Approach: BFS treating board as graph, handle board coordinate mapping
 * Time: O(N^2), Space: O(N^2)
 * Production Analogy: Finding minimum steps in state machine with shortcuts and setbacks
 */
public class Problem12_SnakesAndLadders {
    public int snakesAndLadders(int[][] board) {
        int n = board.length, target = n * n;
        Queue<Integer> q = new LinkedList<>();
        boolean[] visited = new boolean[target + 1];
        q.offer(1); visited[1] = true;
        int moves = 0;
        while (!q.isEmpty()) {
            int size = q.size(); moves++;
            for (int i = 0; i < size; i++) {
                int curr = q.poll();
                for (int dice = 1; dice <= 6; dice++) {
                    int next = curr + dice;
                    if (next > target) continue;
                    int[] rc = getCoord(next, n);
                    if (board[rc[0]][rc[1]] != -1) next = board[rc[0]][rc[1]];
                    if (next == target) return moves;
                    if (!visited[next]) { visited[next] = true; q.offer(next); }
                }
            }
        }
        return -1;
    }

    private int[] getCoord(int pos, int n) {
        int r = (pos - 1) / n, c = (pos - 1) % n;
        if (r % 2 == 1) c = n - 1 - c;
        return new int[]{n - 1 - r, c};
    }

    public static void main(String[] args) {
        int[][] board = {{-1,-1,-1,-1,-1,-1},{-1,-1,-1,-1,-1,-1},{-1,-1,-1,-1,-1,-1},{-1,35,-1,-1,13,-1},{-1,-1,-1,-1,-1,-1},{-1,15,-1,-1,-1,-1}};
        System.out.println(new Problem12_SnakesAndLadders().snakesAndLadders(board)); // 4
    }
}
