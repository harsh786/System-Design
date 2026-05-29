import java.util.*;

public class Problem10_OpenTheLock {
    public static int openLock(String[] deadends, String target) {
        Set<String> dead = new HashSet<>(Arrays.asList(deadends));
        if (dead.contains("0000")) return -1;
        Queue<String> q = new LinkedList<>();
        q.offer("0000"); dead.add("0000");
        int steps = 0;
        while (!q.isEmpty()) {
            for (int sz = q.size(); sz > 0; sz--) {
                String cur = q.poll();
                if (cur.equals(target)) return steps;
                for (int i = 0; i < 4; i++) {
                    for (int d : new int[]{1, -1}) {
                        char[] arr = cur.toCharArray();
                        arr[i] = (char)((arr[i] - '0' + d + 10) % 10 + '0');
                        String next = new String(arr);
                        if (!dead.contains(next)) { dead.add(next); q.offer(next); }
                    }
                }
            }
            steps++;
        }
        return -1;
    }
    public static void main(String[] args) {
        System.out.println(openLock(new String[]{"0201","0101","0102","1212","2002"}, "0202")); // 6
    }
}
