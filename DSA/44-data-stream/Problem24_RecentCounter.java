import java.util.*;

public class Problem24_RecentCounter {
    // 933. Recent Counter (same as #5 but standalone implementation).
    
    Deque<Integer> dq = new ArrayDeque<>();
    
    public int ping(int t) {
        dq.addLast(t);
        while (dq.peekFirst() < t - 3000) dq.pollFirst();
        return dq.size();
    }
    
    public static void main(String[] args) {
        Problem24_RecentCounter sol = new Problem24_RecentCounter();
        System.out.println(sol.ping(1));    // 1
        System.out.println(sol.ping(100));  // 2
        System.out.println(sol.ping(3001)); // 3
        System.out.println(sol.ping(3002)); // 3
    }
}
