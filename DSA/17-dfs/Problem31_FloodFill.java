/**
 * Problem: Flood Fill (LeetCode 733)
 * Approach: DFS from starting pixel, change color of connected same-color pixels
 * Time: O(M*N), Space: O(M*N)
 * Production Analogy: Cascading configuration updates to related service instances
 */
public class Problem31_FloodFill {
    public int[][] floodFill(int[][] image, int sr, int sc, int color) {
        if (image[sr][sc] == color) return image;
        dfs(image, sr, sc, image[sr][sc], color);
        return image;
    }

    private void dfs(int[][] image, int i, int j, int oldColor, int newColor) {
        if (i < 0 || i >= image.length || j < 0 || j >= image[0].length || image[i][j] != oldColor) return;
        image[i][j] = newColor;
        dfs(image, i+1, j, oldColor, newColor); dfs(image, i-1, j, oldColor, newColor);
        dfs(image, i, j+1, oldColor, newColor); dfs(image, i, j-1, oldColor, newColor);
    }

    public static void main(String[] args) {
        int[][] image = {{1,1,1},{1,1,0},{1,0,1}};
        int[][] res = new Problem31_FloodFill().floodFill(image, 1, 1, 2);
        for (int[] row : res) System.out.println(java.util.Arrays.toString(row));
    }
}
