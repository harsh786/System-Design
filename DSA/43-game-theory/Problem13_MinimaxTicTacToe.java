import java.util.*;

public class Problem13_MinimaxTicTacToe {
    // Minimax Tic-Tac-Toe: Find best move using minimax algorithm.
    
    public int minimax(char[] board, boolean isMax) {
        int score = evaluate(board);
        if (score != 0) return score;
        if (isFull(board)) return 0;
        
        int best = isMax ? Integer.MIN_VALUE : Integer.MAX_VALUE;
        for (int i = 0; i < 9; i++) {
            if (board[i] == '.') {
                board[i] = isMax ? 'X' : 'O';
                int val = minimax(board, !isMax);
                best = isMax ? Math.max(best, val) : Math.min(best, val);
                board[i] = '.';
            }
        }
        return best;
    }
    
    private int evaluate(char[] b) {
        int[][] lines = {{0,1,2},{3,4,5},{6,7,8},{0,3,6},{1,4,7},{2,5,8},{0,4,8},{2,4,6}};
        for (int[] l : lines) {
            if (b[l[0]] != '.' && b[l[0]] == b[l[1]] && b[l[1]] == b[l[2]])
                return b[l[0]] == 'X' ? 1 : -1;
        }
        return 0;
    }
    
    private boolean isFull(char[] b) {
        for (char c : b) if (c == '.') return false;
        return true;
    }
    
    public int bestMove(char[] board, boolean isMax) {
        int bestVal = isMax ? Integer.MIN_VALUE : Integer.MAX_VALUE;
        int bestMove = -1;
        for (int i = 0; i < 9; i++) {
            if (board[i] == '.') {
                board[i] = isMax ? 'X' : 'O';
                int val = minimax(board, !isMax);
                board[i] = '.';
                if (isMax && val > bestVal || !isMax && val < bestVal) {
                    bestVal = val; bestMove = i;
                }
            }
        }
        return bestMove;
    }
    
    public static void main(String[] args) {
        Problem13_MinimaxTicTacToe sol = new Problem13_MinimaxTicTacToe();
        char[] board = "X..O.....".toCharArray();
        System.out.println("Best move for X: " + sol.bestMove(board, true));
        System.out.println("Minimax from empty: " + sol.minimax(".........".toCharArray(), true)); // 0 (draw)
    }
}
