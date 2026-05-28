import java.util.*;

/**
 * Problem: Sliding Puzzle (LeetCode 773)
 * Approach: BFS on board states represented as strings
 * Time: O(6! * 6), Space: O(6!)
 * Production Analogy: Finding minimum state transitions in configuration management
 */
public class Problem24_SlidingPuzzle {
    public int slidingPuzzle(int[][] board) {
        String target = "123450";
        StringBuilder sb = new StringBuilder();
        for (int[] row : board) for (int v : row) sb.append(v);
        String start = sb.toString();
        if (start.equals(target)) return 0;
        int[][] swaps = {{1,3},{0,2,4},{1,5},{0,4},{1,3,5},{2,4}};
        Queue<String> q = new LinkedList<>();
        Set<String> visited = new HashSet<>();
        q.offer(start); visited.add(start);
        int moves = 0;
        while (!q.isEmpty()) {
            int size = q.size(); moves++;
            for (int i = 0; i < size; i++) {
                String curr = q.poll();
                int zeroIdx = curr.indexOf('0');
                for (int swap : swaps[zeroIdx]) {
                    char[] arr = curr.toCharArray();
                    arr[zeroIdx] = arr[swap]; arr[swap] = '0';
                    String next = new String(arr);
                    if (next.equals(target)) return moves;
                    if (visited.add(next)) q.offer(next);
                }
            }
        }
        return -1;
    }

    public static void main(String[] args) {
        int[][] board = {{1,2,3},{4,0,5}};
        System.out.println(new Problem24_SlidingPuzzle().slidingPuzzle(board)); // 1
    }
}
