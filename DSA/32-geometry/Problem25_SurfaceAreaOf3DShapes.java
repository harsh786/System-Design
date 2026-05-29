public class Problem25_SurfaceAreaOf3DShapes {
    public static int surfaceArea(int[][] grid) {
        int n = grid.length, area = 0;
        for (int i = 0; i < n; i++) for (int j = 0; j < n; j++) {
            if (grid[i][j] > 0) {
                area += 2 + 4 * grid[i][j];
                if (i > 0) area -= 2 * Math.min(grid[i][j], grid[i-1][j]);
                if (j > 0) area -= 2 * Math.min(grid[i][j], grid[i][j-1]);
            }
        }
        return area;
    }
    public static void main(String[] args) {
        System.out.println(surfaceArea(new int[][]{{1,2},{3,4}})); // 34
    }
}
