import java.util.*;

/**
 * Problem 35: Android Unlock Patterns (LeetCode 351)
 * 
 * Count number of valid unlock patterns of length [m, n] on a 3x3 grid.
 * A pattern is valid if it visits each dot at most once and doesn't skip dots
 * (unless the skipped dot is already visited).
 * 
 * Search Tree:
 * - Start from each dot, DFS to all reachable unvisited dots
 * - A dot is reachable if there's no unvisited dot in between
 * 
 * Pruning Strategy:
 * - Use skip[][] array: skip[i][j] = dot that must be visited to go from i to j
 * - Exploit symmetry: patterns starting from 1,3,7,9 are equivalent (x4)
 *   patterns starting from 2,4,6,8 are equivalent (x4), corner vs edge vs center
 * 
 * Time Complexity: O(n!) bounded by grid size (9! max)
 * Space Complexity: O(9)
 * 
 * Production Analogy:
 * - Enumerating valid state machine transitions with prerequisite constraints.
 */
public class Problem35_AndroidUnlockPatterns {

    public int numberOfPatterns(int m, int n) {
        int[][] skip = new int[10][10];
        skip[1][3] = skip[3][1] = 2;
        skip[1][7] = skip[7][1] = 4;
        skip[3][9] = skip[9][3] = 6;
        skip[7][9] = skip[9][7] = 8;
        skip[1][9] = skip[9][1] = 5;
        skip[3][7] = skip[7][3] = 5;
        skip[2][8] = skip[8][2] = 5;
        skip[4][6] = skip[6][4] = 5;

        boolean[] visited = new boolean[10];
        int result = 0;
        // Symmetry: corner(1) * 4, edge(2) * 4, center(5) * 1
        for (int len = m; len <= n; len++) {
            visited[1] = true;
            result += dfs(skip, visited, 1, len - 1) * 4;
            visited[1] = false;
            visited[2] = true;
            result += dfs(skip, visited, 2, len - 1) * 4;
            visited[2] = false;
            visited[5] = true;
            result += dfs(skip, visited, 5, len - 1);
            visited[5] = false;
        }
        return result;
    }

    private int dfs(int[][] skip, boolean[] visited, int curr, int remaining) {
        if (remaining == 0) return 1;
        int count = 0;
        for (int next = 1; next <= 9; next++) {
            if (visited[next]) continue;
            int mid = skip[curr][next];
            if (mid != 0 && !visited[mid]) continue; // can't skip unvisited
            visited[next] = true;
            count += dfs(skip, visited, next, remaining - 1);
            visited[next] = false;
        }
        return count;
    }

    public static void main(String[] args) {
        Problem35_AndroidUnlockPatterns sol = new Problem35_AndroidUnlockPatterns();

        System.out.println(sol.numberOfPatterns(1, 1)); // 9
        System.out.println(sol.numberOfPatterns(1, 2)); // 65
        System.out.println(sol.numberOfPatterns(1, 9)); // 389112
    }
}
