import java.util.*;

public class Problem12_JumpGameIII {
    public static boolean canReach(int[] arr, int start) {
        Queue<Integer> q = new LinkedList<>();
        q.offer(start);
        boolean[] visited = new boolean[arr.length];
        visited[start] = true;
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
        System.out.println(canReach(new int[]{4,2,3,0,3,1,2}, 5)); // true
    }
}
