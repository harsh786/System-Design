import java.util.*;

public class Problem36_TicTacToeSolver {
    // Complete Tic-Tac-Toe solver with optimal play detection.
    
    public int solve(char[] board, char player) {
        int winner = checkWinner(board);
        if (winner != 0) return winner;
        if (isFull(board)) return 0;
        
        int best = (player == 'X') ? -2 : 2;
        for (int i = 0; i < 9; i++) {
            if (board[i] != '.') continue;
            board[i] = player;
            int val = solve(board, player == 'X' ? 'O' : 'X');
            board[i] = '.';
            if (player == 'X') best = Math.max(best, val);
            else best = Math.min(best, val);
        }
        return best;
    }
    
    private int checkWinner(char[] b) {
        int[][] lines = {{0,1,2},{3,4,5},{6,7,8},{0,3,6},{1,4,7},{2,5,8},{0,4,8},{2,4,6}};
        for (int[] l : lines) {
            if (b[l[0]] != '.' && b[l[0]] == b[l[1]] && b[l[1]] == b[l[2]])
                return b[l[0]] == 'X' ? 1 : -1;
        }
        return 0;
    }
    
    private boolean isFull(char[] b) { for (char c : b) if (c == '.') return false; return true; }
    
    public static void main(String[] args) {
        Problem36_TicTacToeSolver sol = new Problem36_TicTacToeSolver();
        char[] empty = ".........".toCharArray();
        System.out.println("Empty board result (X starts): " + sol.solve(empty, 'X')); // 0 (draw with optimal play)
    }
}
