/**
 * Problem: Find Winner on a Tic Tac Toe Game (LeetCode 1275)
 * Approach: Track row/col/diag sums per player
 * Complexity: O(moves) time, O(n) space
 * Production Analogy: State tracking in turn-based game servers
 */
public class Problem19_TicTacToeWinner {
    public String tictactoe(int[][] moves) {
        int[] rows = new int[3], cols = new int[3];
        int diag = 0, anti = 0;
        for (int i = 0; i < moves.length; i++) {
            int r = moves[i][0], c = moves[i][1];
            int val = (i%2==0) ? 1 : -1;
            rows[r] += val; cols[c] += val;
            if (r==c) diag += val;
            if (r+c==2) anti += val;
            if (Math.abs(rows[r])==3 || Math.abs(cols[c])==3 || Math.abs(diag)==3 || Math.abs(anti)==3)
                return val==1 ? "A" : "B";
        }
        return moves.length==9 ? "Draw" : "Pending";
    }
    public static void main(String[] args) {
        System.out.println(new Problem19_TicTacToeWinner().tictactoe(
            new int[][]{{0,0},{2,0},{1,1},{2,1},{2,2}})); // A
    }
}
