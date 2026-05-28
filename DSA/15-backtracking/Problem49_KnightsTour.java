import java.util.*;

/**
 * Problem 49: Knight's Tour
 * 
 * Find a sequence of knight moves on an n×n board visiting every square exactly once.
 * 
 * Search Tree:
 * - From current position, try all 8 possible knight moves
 * - Mark visited squares; backtrack if stuck
 * 
 * Pruning Strategy:
 * - Warnsdorff's heuristic: prefer moves to squares with fewest onward moves
 *   (dramatically reduces search time)
 * - Skip visited or out-of-bounds squares
 * 
 * Time Complexity: O(8^(n^2)) worst case without heuristic; near-linear with Warnsdorff
 * Space Complexity: O(n^2)
 * 
 * Production Analogy:
 * - Complete graph traversal with resource constraints (visiting all nodes in a network).
 */
public class Problem49_KnightsTour {

    private static final int[] dx = {2,2,-2,-2,1,1,-1,-1};
    private static final int[] dy = {1,-1,1,-1,2,-2,2,-2};

    public int[][] solve(int n) {
        int[][] board = new int[n][n];
        for (int[] row : board) Arrays.fill(row, -1);
        board[0][0] = 0;
        if (backtrack(board, 0, 0, 1, n)) return board;
        return new int[0][0]; // no solution
    }

    private boolean backtrack(int[][] board, int x, int y, int move, int n) {
        if (move == n * n) return true;
        // Get all valid next moves and sort by Warnsdorff's heuristic
        List<int[]> nextMoves = new ArrayList<>();
        for (int i = 0; i < 8; i++) {
            int nx = x + dx[i], ny = y + dy[i];
            if (nx >= 0 && nx < n && ny >= 0 && ny < n && board[nx][ny] == -1) {
                int degree = countMoves(board, nx, ny, n);
                nextMoves.add(new int[]{nx, ny, degree});
            }
        }
        nextMoves.sort((a, b) -> a[2] - b[2]); // Warnsdorff: fewest onward moves first

        for (int[] nm : nextMoves) {
            board[nm[0]][nm[1]] = move;
            if (backtrack(board, nm[0], nm[1], move + 1, n)) return true;
            board[nm[0]][nm[1]] = -1;
        }
        return false;
    }

    private int countMoves(int[][] board, int x, int y, int n) {
        int count = 0;
        for (int i = 0; i < 8; i++) {
            int nx = x + dx[i], ny = y + dy[i];
            if (nx >= 0 && nx < n && ny >= 0 && ny < n && board[nx][ny] == -1) count++;
        }
        return count;
    }

    public static void main(String[] args) {
        Problem49_KnightsTour sol = new Problem49_KnightsTour();

        int[][] result = sol.solve(8);
        if (result.length > 0) {
            System.out.println("Knight's Tour found for 8x8:");
            for (int[] row : result) System.out.println(Arrays.toString(row));
        }

        int[][] small = sol.solve(5);
        if (small.length > 0) {
            System.out.println("\nKnight's Tour found for 5x5:");
            for (int[] row : small) System.out.println(Arrays.toString(row));
        }
    }
}
