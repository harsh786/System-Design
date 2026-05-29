import java.util.*;

/**
 * Problem: Open the Lock
 * Minimum turns to reach target from "0000" avoiding deadends.
 *
 * Approach: BFS treating each state as a node
 *
 * Time Complexity: O(10^4 * 4) = O(1)
 * Space Complexity: O(10^4)
 *
 * Production Analogy: Finding minimum state transitions avoiding forbidden configurations.
 */
public class Problem07_OpenTheLock {

    public int openLock(String[] deadends, String target) {
        Set<String> dead = new HashSet<>(Arrays.asList(deadends));
        if (dead.contains("0000")) return -1;

        Queue<String> q = new LinkedList<>();
        q.offer("0000");
        Set<String> visited = new HashSet<>();
        visited.add("0000");
        int turns = 0;

        while (!q.isEmpty()) {
            int size = q.size();
            for (int i = 0; i < size; i++) {
                String cur = q.poll();
                if (cur.equals(target)) return turns;
                for (int j = 0; j < 4; j++) {
                    for (int d : new int[]{1, -1}) {
                        char[] arr = cur.toCharArray();
                        arr[j] = (char)((arr[j] - '0' + d + 10) % 10 + '0');
                        String next = new String(arr);
                        if (!dead.contains(next) && visited.add(next)) q.offer(next);
                    }
                }
            }
            turns++;
        }
        return -1;
    }

    public static void main(String[] args) {
        Problem07_OpenTheLock solver = new Problem07_OpenTheLock();
        System.out.println(solver.openLock(new String[]{"0201","0101","0102","1212","2002"}, "0202")); // 6
    }
}
