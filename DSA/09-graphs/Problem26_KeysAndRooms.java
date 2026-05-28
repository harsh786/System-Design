import java.util.*;

/**
 * Problem 26: Keys and Rooms (LeetCode 841)
 * 
 * Approach: BFS/DFS from room 0. Check if all rooms visited.
 * Time: O(V + E), Space: O(V)
 * 
 * Production Analogy: Verifying all services are reachable from the entry point given access tokens.
 */
public class Problem26_KeysAndRooms {
    
    public boolean canVisitAllRooms(List<List<Integer>> rooms) {
        Set<Integer> visited = new HashSet<>();
        Queue<Integer> q = new LinkedList<>();
        q.offer(0); visited.add(0);
        while (!q.isEmpty()) {
            int room = q.poll();
            for (int key : rooms.get(room))
                if (visited.add(key)) q.offer(key);
        }
        return visited.size() == rooms.size();
    }
    
    public static void main(String[] args) {
        Problem26_KeysAndRooms sol = new Problem26_KeysAndRooms();
        System.out.println(sol.canVisitAllRooms(Arrays.asList(Arrays.asList(1),Arrays.asList(2),Arrays.asList(3),Arrays.asList()))); // true
        System.out.println(sol.canVisitAllRooms(Arrays.asList(Arrays.asList(1,3),Arrays.asList(3,0,1),Arrays.asList(2),Arrays.asList(0)))); // false
    }
}
