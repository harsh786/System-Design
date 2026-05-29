import java.util.*;

/**
 * Problem: Strange Printer II
 * Determine if a grid can be printed by printing rectangles of colors in some order.
 *
 * Approach: Build dependency graph (color A must print before color B if A's bounding box
 * contains B's cells), then check for cycles via topological sort.
 *
 * Time Complexity: O(m*n*C + C^2) where C = number of colors (<=60)
 * Space Complexity: O(C^2)
 *
 * Production Analogy: Determining if layered rendering operations can produce a target image.
 */
public class Problem24_StrangePrinterII {

    public boolean isPrintable(int[][] targetGrid) {
        int m = targetGrid.length, n = targetGrid[0].length;
        int[] minR = new int[61], maxR = new int[61], minC = new int[61], maxC = new int[61];
        Arrays.fill(minR, m); Arrays.fill(minC, n);
        Set<Integer> colors = new HashSet<>();

        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++) {
                int c = targetGrid[i][j];
                colors.add(c);
                minR[c] = Math.min(minR[c], i); maxR[c] = Math.max(maxR[c], i);
                minC[c] = Math.min(minC[c], j); maxC[c] = Math.max(maxC[c], j);
            }

        Set<Integer>[] deps = new HashSet[61];
        for (int i = 0; i < 61; i++) deps[i] = new HashSet<>();

        for (int c : colors)
            for (int i = minR[c]; i <= maxR[c]; i++)
                for (int j = minC[c]; j <= maxC[c]; j++)
                    if (targetGrid[i][j] != c) deps[c].add(targetGrid[i][j]);

        // Topological sort to check no cycle
        int[] visited = new int[61];
        for (int c : colors)
            if (visited[c] == 0 && hasCycle(c, deps, visited)) return false;
        return true;
    }

    private boolean hasCycle(int c, Set<Integer>[] deps, int[] visited) {
        visited[c] = 1;
        for (int d : deps[c]) {
            if (visited[d] == 1) return true;
            if (visited[d] == 0 && hasCycle(d, deps, visited)) return true;
        }
        visited[c] = 2;
        return false;
    }

    public static void main(String[] args) {
        Problem24_StrangePrinterII solver = new Problem24_StrangePrinterII();
        System.out.println(solver.isPrintable(new int[][]{{1,1,1,1},{1,2,2,1},{1,2,2,1},{1,1,1,1}})); // true
    }
}
