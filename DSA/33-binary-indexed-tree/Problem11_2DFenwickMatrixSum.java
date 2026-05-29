import java.util.*;

public class Problem11_2DFenwickMatrixSum {
    int[][] bit;
    int rows, cols;

    Problem11_2DFenwickMatrixSum(int m, int n) { rows = m; cols = n; bit = new int[m + 1][n + 1]; }

    void update(int r, int c, int delta) {
        for (int i = r; i <= rows; i += i & (-i))
            for (int j = c; j <= cols; j += j & (-j))
                bit[i][j] += delta;
    }

    int query(int r, int c) {
        int s = 0;
        for (int i = r; i > 0; i -= i & (-i))
            for (int j = c; j > 0; j -= j & (-j))
                s += bit[i][j];
        return s;
    }

    int rangeQuery(int r1, int c1, int r2, int c2) {
        return query(r2, c2) - query(r1 - 1, c2) - query(r2, c1 - 1) + query(r1 - 1, c1 - 1);
    }

    public static void main(String[] args) {
        Problem11_2DFenwickMatrixSum ft = new Problem11_2DFenwickMatrixSum(3, 3);
        ft.update(1, 1, 1); ft.update(2, 2, 2); ft.update(3, 3, 3);
        System.out.println(ft.rangeQuery(1, 1, 3, 3)); // 6
    }
}
