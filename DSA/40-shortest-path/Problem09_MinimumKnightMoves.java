import java.util.*;

/**
 * Problem: Minimum Knight Moves
 * Minimum moves for chess knight to reach (x,y) from (0,0).
 *
 * Approach: BFS / Bidirectional BFS for optimization
 *
 * Time Complexity: O(max(|x|,|y|)^2)
 * Space Complexity: O(max(|x|,|y|)^2)
 *
 * Production Analogy: Finding minimum hops in an irregular network topology.
 */
public class Problem09_MinimumKnightMoves {

    public int minKnightMoves(int x, int y) {
        x = Math.abs(x); y = Math.abs(y);
        int[][] dirs = {{2,1},{1,2},{-1,2},{-2,1},{-2,-1},{-1,-2},{1,-2},{2,-1}};

        Queue<int[]> q = new LinkedList<>();
        q.offer(new int[]{0, 0});
        Set<String> visited = new HashSet<>();
        visited.add("0,0");
        int steps = 0;

        while (!q.isEmpty()) {
            int size = q.size();
            for (int i = 0; i < size; i++) {
                int[] cur = q.poll();
                if (cur[0] == x && cur[1] == y) return steps;
                for (int[] d : dirs) {
                    int nx = cur[0]+d[0], ny = cur[1]+d[1];
                    if (nx >= -2 && ny >= -2 && nx <= x+2 && ny <= y+2) {
                        String key = nx + "," + ny;
                        if (visited.add(key)) q.offer(new int[]{nx, ny});
                    }
                }
            }
            steps++;
        }
        return -1;
    }

    public static void main(String[] args) {
        Problem09_MinimumKnightMoves solver = new Problem09_MinimumKnightMoves();
        System.out.println(solver.minKnightMoves(5, 5)); // 4
    }
}
