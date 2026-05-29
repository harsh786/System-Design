package segmenttree;

/**
 * Problem 18: 2D Segment Tree (Range Sum Query 2D - Mutable style)
 * 
 * Approach: Segment tree of segment trees. Outer tree on rows, inner trees on columns.
 * 
 * Time Complexity: O(log n * log m) per update/query
 * Space Complexity: O(n * m)
 */
public class Problem18_2DSegmentTree {
    
    private int[][] tree;
    private int n, m;
    
    public Problem18_2DSegmentTree(int[][] matrix) {
        if (matrix.length == 0) return;
        n = matrix.length; m = matrix[0].length;
        tree = new int[4 * n][4 * m];
        buildX(1, 0, n - 1, matrix);
    }
    
    private void buildX(int nx, int lx, int rx, int[][] mat) {
        if (lx == rx) { buildY(nx, 1, 0, m - 1, lx, mat); return; }
        int mid = (lx + rx) / 2;
        buildX(2 * nx, lx, mid, mat);
        buildX(2 * nx + 1, mid + 1, rx, mat);
        for (int i = 0; i < 4 * m; i++) tree[nx][i] = tree[2 * nx][i] + tree[2 * nx + 1][i];
    }
    
    private void buildY(int nx, int ny, int ly, int ry, int row, int[][] mat) {
        if (ly == ry) { tree[nx][ny] = mat[row][ly]; return; }
        int mid = (ly + ry) / 2;
        buildY(nx, 2 * ny, ly, mid, row, mat);
        buildY(nx, 2 * ny + 1, mid + 1, ry, row, mat);
        tree[nx][ny] = tree[nx][2 * ny] + tree[nx][2 * ny + 1];
    }
    
    public void update(int row, int col, int val) { updateX(1, 0, n - 1, row, col, val); }
    
    private void updateX(int nx, int lx, int rx, int row, int col, int val) {
        if (lx == rx) { updateY(nx, 1, 0, m - 1, col, val, true); return; }
        int mid = (lx + rx) / 2;
        if (row <= mid) updateX(2 * nx, lx, mid, row, col, val);
        else updateX(2 * nx + 1, mid + 1, rx, row, col, val);
        updateY(nx, 1, 0, m - 1, col, val, false);
    }
    
    private void updateY(int nx, int ny, int ly, int ry, int col, int val, boolean leaf) {
        if (ly == ry) {
            tree[nx][ny] = leaf ? val : tree[2 * nx][ny] + tree[2 * nx + 1][ny];
            return;
        }
        int mid = (ly + ry) / 2;
        if (col <= mid) updateY(nx, 2 * ny, ly, mid, col, val, leaf);
        else updateY(nx, 2 * ny + 1, mid + 1, ry, col, val, leaf);
        tree[nx][ny] = tree[nx][2 * ny] + tree[nx][2 * ny + 1];
    }
    
    public int query(int r1, int c1, int r2, int c2) { return queryX(1, 0, n - 1, r1, r2, c1, c2); }
    
    private int queryX(int nx, int lx, int rx, int r1, int r2, int c1, int c2) {
        if (r2 < lx || rx < r1) return 0;
        if (r1 <= lx && rx <= r2) return queryY(nx, 1, 0, m - 1, c1, c2);
        int mid = (lx + rx) / 2;
        return queryX(2 * nx, lx, mid, r1, r2, c1, c2) + queryX(2 * nx + 1, mid + 1, rx, r1, r2, c1, c2);
    }
    
    private int queryY(int nx, int ny, int ly, int ry, int c1, int c2) {
        if (c2 < ly || ry < c1) return 0;
        if (c1 <= ly && ry <= c2) return tree[nx][ny];
        int mid = (ly + ry) / 2;
        return queryY(nx, 2 * ny, ly, mid, c1, c2) + queryY(nx, 2 * ny + 1, mid + 1, ry, c1, c2);
    }
    
    public static void main(String[] args) {
        int[][] mat = {{1,2,3},{4,5,6},{7,8,9}};
        Problem18_2DSegmentTree st = new Problem18_2DSegmentTree(mat);
        System.out.println(st.query(0, 0, 2, 2)); // 45
        System.out.println(st.query(1, 1, 2, 2)); // 28
        st.update(1, 1, 10);
        System.out.println(st.query(1, 1, 2, 2)); // 33
    }
}
