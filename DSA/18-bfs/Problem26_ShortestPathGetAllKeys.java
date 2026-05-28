import java.util.*;

/**
 * Problem: Shortest Path to Get All Keys (LeetCode 864)
 * Approach: BFS with state (row, col, keys_bitmask)
 * Time: O(M*N*2^K), Space: O(M*N*2^K) K=number of keys
 * Production Analogy: Minimum steps in workflow requiring progressive credential acquisition
 */
public class Problem26_ShortestPathGetAllKeys {
    public int shortestPathAllKeys(String[] grid) {
        int m = grid.length, n = grid[0].length(), allKeys = 0;
        Queue<int[]> q = new LinkedList<>();
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++) {
                char c = grid[i].charAt(j);
                if (c == '@') q.offer(new int[]{i, j, 0});
                if (c >= 'a' && c <= 'f') allKeys |= (1 << (c - 'a'));
            }
        Set<String> visited = new HashSet<>();
        visited.add(q.peek()[0] + "," + q.peek()[1] + ",0");
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        int steps = 0;
        while (!q.isEmpty()) {
            int size = q.size(); steps++;
            for (int i = 0; i < size; i++) {
                int[] curr = q.poll();
                for (int[] d : dirs) {
                    int ni = curr[0]+d[0], nj = curr[1]+d[1], keys = curr[2];
                    if (ni < 0 || ni >= m || nj < 0 || nj >= n) continue;
                    char c = grid[ni].charAt(nj);
                    if (c == '#') continue;
                    if (c >= 'A' && c <= 'F' && (keys & (1 << (c - 'A'))) == 0) continue;
                    int newKeys = keys;
                    if (c >= 'a' && c <= 'f') newKeys |= (1 << (c - 'a'));
                    if (newKeys == allKeys) return steps;
                    String key = ni + "," + nj + "," + newKeys;
                    if (visited.add(key)) q.offer(new int[]{ni, nj, newKeys});
                }
            }
        }
        return -1;
    }

    public static void main(String[] args) {
        System.out.println(new Problem26_ShortestPathGetAllKeys().shortestPathAllKeys(new String[]{"@.a..","###.#","b.A.B"})); // 8
    }
}
