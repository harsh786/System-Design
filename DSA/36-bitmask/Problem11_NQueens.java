import java.util.*;

public class Problem11_NQueens {
    public List<List<String>> solveNQueens(int n) {
        List<List<String>> result = new ArrayList<>();
        solve(result, new int[n], 0, n, 0, 0, 0);
        return result;
    }

    private void solve(List<List<String>> result, int[] queens, int row, int n, int cols, int d1, int d2) {
        if (row == n) {
            List<String> board = new ArrayList<>();
            for (int q : queens) { char[] r = new char[n]; Arrays.fill(r, '.'); r[q] = 'Q'; board.add(new String(r)); }
            result.add(board); return;
        }
        int available = ((1 << n) - 1) & ~(cols | d1 | d2);
        while (available != 0) {
            int bit = available & -available; available -= bit;
            int col = Integer.numberOfTrailingZeros(bit);
            queens[row] = col;
            solve(result, queens, row + 1, n, cols | bit, (d1 | bit) << 1, (d2 | bit) >> 1);
        }
    }

    public static void main(String[] args) {
        System.out.println(new Problem11_NQueens().solveNQueens(4).size());
    }
}
