import java.util.*;

/**
 * Problem: Jump Game III (LeetCode 1306)
 * Approach: BFS from start index, jump +/- arr[i] positions
 * Time: O(N), Space: O(N)
 * Production Analogy: Reachability analysis in state machine with variable-length transitions
 */
public class Problem16_JumpGameIII {
    public boolean canReach(int[] arr, int start) {
        Queue<Integer> q = new LinkedList<>();
        boolean[] visited = new boolean[arr.length];
        q.offer(start); visited[start] = true;
        while (!q.isEmpty()) {
            int i = q.poll();
            if (arr[i] == 0) return true;
            for (int next : new int[]{i + arr[i], i - arr[i]}) {
                if (next >= 0 && next < arr.length && !visited[next]) {
                    visited[next] = true; q.offer(next);
                }
            }
        }
        return false;
    }

    public static void main(String[] args) {
        System.out.println(new Problem16_JumpGameIII().canReach(new int[]{4,2,3,0,3,1,2}, 5)); // true
    }
}
