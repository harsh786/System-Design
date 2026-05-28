import java.util.*;

/**
 * Problem: Open the Lock (LeetCode 752)
 * Approach: BFS from "0000", each state has 8 neighbors (4 dials * 2 directions)
 * Time: O(10^4 * 8), Space: O(10^4)
 * Production Analogy: Finding minimum configuration changes to reach target state avoiding invalid states
 */
public class Problem04_OpenTheLock {
    public int openLock(String[] deadends, String target) {
        Set<String> dead = new HashSet<>(Arrays.asList(deadends));
        if (dead.contains("0000")) return -1;
        Queue<String> q = new LinkedList<>();
        q.offer("0000");
        Set<String> visited = new HashSet<>();
        visited.add("0000");
        int steps = 0;
        while (!q.isEmpty()) {
            int size = q.size();
            for (int i = 0; i < size; i++) {
                String curr = q.poll();
                if (curr.equals(target)) return steps;
                for (String next : neighbors(curr)) {
                    if (!visited.contains(next) && !dead.contains(next)) {
                        visited.add(next); q.offer(next);
                    }
                }
            }
            steps++;
        }
        return -1;
    }

    private List<String> neighbors(String s) {
        List<String> res = new ArrayList<>();
        char[] arr = s.toCharArray();
        for (int i = 0; i < 4; i++) {
            char orig = arr[i];
            arr[i] = orig == '9' ? '0' : (char)(orig + 1); res.add(new String(arr));
            arr[i] = orig == '0' ? '9' : (char)(orig - 1); res.add(new String(arr));
            arr[i] = orig;
        }
        return res;
    }

    public static void main(String[] args) {
        System.out.println(new Problem04_OpenTheLock().openLock(new String[]{"0201","0101","0102","1212","2002"}, "0202")); // 6
    }
}
