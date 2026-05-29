public class Problem24_ProjectionAreaOf3DShapes {
    public static int projectionArea(int[][] grid) {
        int n = grid.length, xy = 0, xz = 0, yz = 0;
        for (int i = 0; i < n; i++) {
            int maxRow = 0, maxCol = 0;
            for (int j = 0; j < n; j++) {
                if (grid[i][j] > 0) xy++;
                maxRow = Math.max(maxRow, grid[i][j]);
                maxCol = Math.max(maxCol, grid[j][i]);
            }
            xz += maxRow; yz += maxCol;
        }
        return xy + xz + yz;
    }
    public static void main(String[] args) {
        System.out.println(projectionArea(new int[][]{{1,2},{3,4}})); // 17
    }
}
