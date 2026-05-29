import java.util.*;

public class Problem05_NumberOfRecentCalls {
    // 933. Number of Recent Calls.
    
    Queue<Integer> queue = new LinkedList<>();
    
    public int ping(int t) {
        queue.offer(t);
        while (queue.peek() < t - 3000) queue.poll();
        return queue.size();
    }
    
    public static void main(String[] args) {
        Problem05_NumberOfRecentCalls sol = new Problem05_NumberOfRecentCalls();
        System.out.println(sol.ping(1));    // 1
        System.out.println(sol.ping(100));  // 2
        System.out.println(sol.ping(3001)); // 3
        System.out.println(sol.ping(3002)); // 3
    }
}
