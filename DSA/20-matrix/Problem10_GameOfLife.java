import java.util.*;

/**
 * Problem 10: Game of Life
 * 
 * Apply Conway's Game of Life rules simultaneously to all cells.
 *
 * Approach: Encode state transitions in-place using extra bits.
 * 2 = was dead, now alive. 3 = was alive, now dead (we use different encoding).
 * Actually: use bit 1 for next state: current in bit 0, next in bit 1.
 *
 * Time Complexity: O(m * n)
 * Space Complexity: O(1)
 *
 * Production Analogy: Simulating distributed system state transitions where all nodes
 * update simultaneously based on neighbor states - like cellular automata in network simulations.
 */
public class Problem10_GameOfLife {

    public static void gameOfLife(int[][] board) {
        int m = board.length, n = board[0].length;
        int[] dx = {-1,-1,-1,0,0,1,1,1}, dy = {-1,0,1,-1,1,-1,0,1};

        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++) {
                int live = 0;
                for (int d = 0; d < 8; d++) {
                    int ni = i + dx[d], nj = j + dy[d];
                    if (ni >= 0 && ni < m && nj >= 0 && nj < n)
                        live += board[ni][nj] & 1;
                }
                if ((board[i][j] & 1) == 1) {
                    if (live == 2 || live == 3) board[i][j] |= 2;
                } else {
                    if (live == 3) board[i][j] |= 2;
                }
            }

        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++)
                board[i][j] >>= 1;
    }

    public static void main(String[] args) {
        int[][] b1 = {{0,1,0},{0,0,1},{1,1,1},{0,0,0}};
        gameOfLife(b1);
        System.out.println("Test 1: " + Arrays.deepToString(b1));
        // [[0,0,0],[1,0,1],[0,1,1],[0,1,0]]

        int[][] b2 = {{1,1},{1,0}};
        gameOfLife(b2);
        System.out.println("Test 2: " + Arrays.deepToString(b2));
    }
}
