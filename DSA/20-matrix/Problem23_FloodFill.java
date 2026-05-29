import java.util.*;

/**
 * Problem 23: Flood Fill
 * 
 * Starting from pixel (sr, sc), change all connected same-color pixels to newColor.
 *
 * Approach: DFS from starting pixel.
 *
 * Time Complexity: O(m * n)
 * Space Complexity: O(m * n) recursion
 *
 * Production Analogy: Paint bucket tool in image editors. Also analogous to
 * propagating a configuration change across a cluster of same-state nodes.
 */
public class Problem23_FloodFill {

    public static int[][] floodFill(int[][] image, int sr, int sc, int color) {
        int origColor = image[sr][sc];
        if (origColor != color) dfs(image, sr, sc, origColor, color);
        return image;
    }

    private static void dfs(int[][] image, int i, int j, int orig, int color) {
        if (i < 0 || i >= image.length || j < 0 || j >= image[0].length || image[i][j] != orig) return;
        image[i][j] = color;
        dfs(image, i+1, j, orig, color);
        dfs(image, i-1, j, orig, color);
        dfs(image, i, j+1, orig, color);
        dfs(image, i, j-1, orig, color);
    }

    public static void main(String[] args) {
        int[][] img = {{1,1,1},{1,1,0},{1,0,1}};
        System.out.println("Test 1: " + Arrays.deepToString(floodFill(img, 1, 1, 2)));
        // [[2,2,2],[2,2,0],[2,0,1]]

        int[][] img2 = {{0,0,0},{0,0,0}};
        System.out.println("Test 2: " + Arrays.deepToString(floodFill(img2, 0, 0, 0)));
    }
}
