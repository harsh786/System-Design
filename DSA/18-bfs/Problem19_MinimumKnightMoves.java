import java.util.*;

/**
 * Problem: Minimum Knight Moves (LeetCode 1197)
 * Approach: BFS from origin, exploit symmetry by working in first quadrant
 * Time: O(|x|*|y|), Space: O(|x|*|y|)
 * Production Analogy: Minimum hops in a constrained routing topology
 */
public class Problem19_MinimumKnightMoves {
    public int minKnightMoves(int x, int y) {
        x = Math.abs(x); y = Math.abs(y);
        int[][] dirs = {{1,2},{2,1},{2,-1},{1,-2},{-1,-2},{-2,-1},{-2,1},{-1,2}};
        Queue<int[]> q = new LinkedList<>();
        Set<String> visited = new HashSet<>();
        q.offer(new int[]{0, 0}); visited.add("0,0");
        int steps = 0;
        while (!q.isEmpty()) {
            int size = q.size();
            for (int i = 0; i < size; i++) {
                int[] curr = q.poll();
                if (curr[0] == x && curr[1] == y) return steps;
                for (int[] d : dirs) {
                    int nx = curr[0]+d[0], ny = curr[1]+d[1];
                    String key = nx + "," + ny;
                    if (nx >= -2 && ny >= -2 && !visited.contains(key)) {
                        visited.add(key); q.offer(new int[]{nx, ny});
                    }
                }
            }
            steps++;
        }
        return -1;
    }

    public static void main(String[] args) {
        System.out.println(new Problem19_MinimumKnightMoves().minKnightMoves(5, 5)); // 4
    }
}
