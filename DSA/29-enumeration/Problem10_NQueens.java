import java.util.*;

public class Problem10_NQueens {
    public List<List<String>> solveNQueens(int n) {
        List<List<String>> result = new ArrayList<>();
        backtrack(result, new int[n], 0, n);
        return result;
    }

    private void backtrack(List<List<String>> result, int[] queens, int row, int n) {
        if (row == n) {
            List<String> board = new ArrayList<>();
            for (int q : queens) { char[] r = new char[n]; Arrays.fill(r,'.'); r[q]='Q'; board.add(new String(r)); }
            result.add(board); return;
        }
        for (int col = 0; col < n; col++) {
            boolean valid = true;
            for (int i = 0; i < row; i++) if (queens[i]==col||Math.abs(queens[i]-col)==row-i) { valid=false; break; }
            if (valid) { queens[row]=col; backtrack(result,queens,row+1,n); }
        }
    }

    public static void main(String[] args) { System.out.println(new Problem10_NQueens().solveNQueens(4).size()); }
}
