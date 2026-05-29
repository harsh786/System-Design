public class Problem45_NQueensII {
    static int count;
    public static int totalNQueens(int n) {
        count = 0;
        solve(new boolean[n], new boolean[2*n], new boolean[2*n], 0, n);
        return count;
    }
    static void solve(boolean[] cols, boolean[] diag1, boolean[] diag2, int row, int n) {
        if (row == n) { count++; return; }
        for (int col = 0; col < n; col++) {
            if (cols[col] || diag1[row - col + n] || diag2[row + col]) continue;
            cols[col] = diag1[row - col + n] = diag2[row + col] = true;
            solve(cols, diag1, diag2, row + 1, n);
            cols[col] = diag1[row - col + n] = diag2[row + col] = false;
        }
    }
    public static void main(String[] args) {
        System.out.println(totalNQueens(4)); // 2
        System.out.println(totalNQueens(8)); // 92
    }
}
