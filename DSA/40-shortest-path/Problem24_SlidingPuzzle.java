import java.util.*;

/**
 * Problem: Sliding Puzzle
 * Minimum moves to solve 2x3 sliding puzzle.
 *
 * Approach: BFS with board state as string
 *
 * Time Complexity: O(6!)
 * Space Complexity: O(6!)
 *
 * Production Analogy: Finding minimum configuration changes to reach desired system state.
 */
public class Problem24_SlidingPuzzle {

    public int slidingPuzzle(int[][] board) {
        String target = "123450";
        StringBuilder sb = new StringBuilder();
        for (int[] row : board) for (int v : row) sb.append(v);
        String start = sb.toString();
        if (start.equals(target)) return 0;

        int[][] moves = {{1,3},{0,2,4},{1,5},{0,4},{1,3,5},{2,4}};
        Queue<String> q = new LinkedList<>();
        Set<String> visited = new HashSet<>();
        q.offer(start); visited.add(start);
        int steps = 0;

        while (!q.isEmpty()) {
            steps++;
            int size = q.size();
            for (int i = 0; i < size; i++) {
                String cur = q.poll();
                int zero = cur.indexOf('0');
                for (int next : moves[zero]) {
                    char[] arr = cur.toCharArray();
                    arr[zero] = arr[next]; arr[next] = '0';
                    String s = new String(arr);
                    if (s.equals(target)) return steps;
                    if (visited.add(s)) q.offer(s);
                }
            }
        }
        return -1;
    }

    public static void main(String[] args) {
        Problem24_SlidingPuzzle solver = new Problem24_SlidingPuzzle();
        System.out.println(solver.slidingPuzzle(new int[][]{{1,2,3},{4,0,5}})); // 1
    }
}
