import java.util.*;

/**
 * Problem: Keys and Rooms BFS (LeetCode 841)
 * Approach: BFS from room 0 using collected keys
 * Time: O(V+E), Space: O(V)
 * Production Analogy: Progressive access unlocking via credential propagation
 */
public class Problem39_KeysAndRoomsBFS {
    public boolean canVisitAllRooms(List<List<Integer>> rooms) {
        boolean[] visited = new boolean[rooms.size()];
        Queue<Integer> q = new LinkedList<>();
        q.offer(0); visited[0] = true;
        int count = 1;
        while (!q.isEmpty()) {
            int room = q.poll();
            for (int key : rooms.get(room)) {
                if (!visited[key]) { visited[key] = true; count++; q.offer(key); }
            }
        }
        return count == rooms.size();
    }

    public static void main(String[] args) {
        List<List<Integer>> rooms = Arrays.asList(Arrays.asList(1),Arrays.asList(2),Arrays.asList(3),Arrays.asList());
        System.out.println(new Problem39_KeysAndRoomsBFS().canVisitAllRooms(rooms)); // true
    }
}
