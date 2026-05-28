import java.util.*;

/**
 * Problem: Keys and Rooms (LeetCode 841)
 * Approach: DFS from room 0, collecting keys to unlock other rooms
 * Time: O(V+E), Space: O(V)
 * Production Analogy: Access control propagation - determining reachable resources from initial permissions
 */
public class Problem30_KeysAndRooms {
    public boolean canVisitAllRooms(List<List<Integer>> rooms) {
        boolean[] visited = new boolean[rooms.size()];
        dfs(rooms, 0, visited);
        for (boolean v : visited) if (!v) return false;
        return true;
    }

    private void dfs(List<List<Integer>> rooms, int room, boolean[] visited) {
        visited[room] = true;
        for (int key : rooms.get(room))
            if (!visited[key]) dfs(rooms, key, visited);
    }

    public static void main(String[] args) {
        List<List<Integer>> rooms = Arrays.asList(Arrays.asList(1),Arrays.asList(2),Arrays.asList(3),Arrays.asList());
        System.out.println(new Problem30_KeysAndRooms().canVisitAllRooms(rooms)); // true
    }
}
