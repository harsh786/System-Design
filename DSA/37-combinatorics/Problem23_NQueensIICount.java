public class Problem23_NQueensIICount {
    int count = 0;

    public int totalNQueens(int n) {
        backtrack(0, n, 0, 0, 0);
        return count;
    }

    private void backtrack(int row, int n, int cols, int diag1, int diag2) {
        if (row == n) { count++; return; }
        int available = ((1 << n) - 1) & ~(cols | diag1 | diag2);
        while (available != 0) {
            int pos = available & (-available);
            available -= pos;
            backtrack(row + 1, n, cols | pos, (diag1 | pos) << 1, (diag2 | pos) >> 1);
        }
    }

    public static void main(String[] args) {
        System.out.println(new Problem23_NQueensIICount().totalNQueens(8)); // 92
    }
}
