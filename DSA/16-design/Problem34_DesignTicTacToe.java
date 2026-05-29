import java.util.*;

/**
 * Problem 34: Design Tic-Tac-Toe
 * 
 * API Contract:
 * - move(row, col, player): Player (1 or 2) places mark. Return winner (1/2) or 0.
 * 
 * Complexity: O(1) per move
 * Data Structure: Row/col/diagonal counters per player (player1 = +1, player2 = -1)
 * 
 * Production Analogy: Game state validation, real-time win condition checking,
 * constraint satisfaction in rule engines
 */
public class Problem34_DesignTicTacToe {

    static class TicTacToe {
        private int[] rows, cols;
        private int diag, antiDiag, n;

        public TicTacToe(int n) {
            this.n = n;
            rows = new int[n];
            cols = new int[n];
        }

        public int move(int row, int col, int player) {
            int add = player == 1 ? 1 : -1;
            rows[row] += add;
            cols[col] += add;
            if (row == col) diag += add;
            if (row + col == n - 1) antiDiag += add;
            if (Math.abs(rows[row]) == n || Math.abs(cols[col]) == n ||
                Math.abs(diag) == n || Math.abs(antiDiag) == n)
                return player;
            return 0;
        }
    }

    public static void main(String[] args) {
        TicTacToe game = new TicTacToe(3);
        assert game.move(0, 0, 1) == 0;
        assert game.move(0, 2, 2) == 0;
        assert game.move(2, 2, 1) == 0;
        assert game.move(1, 1, 2) == 0;
        assert game.move(2, 0, 1) == 0;
        assert game.move(1, 0, 2) == 0;
        assert game.move(2, 1, 1) == 1; // row 2 complete

        // Diagonal win
        TicTacToe g2 = new TicTacToe(3);
        g2.move(0, 0, 1); g2.move(0, 1, 2);
        g2.move(1, 1, 1); g2.move(0, 2, 2);
        assert g2.move(2, 2, 1) == 1; // diagonal

        System.out.println("All tests passed!");
    }
}
