import java.util.*;

public class Problem07_HitCounter {
    // 362. Design Hit Counter.
    
    Queue<Integer> queue = new LinkedList<>();
    
    public void hit(int timestamp) { queue.offer(timestamp); }
    
    public int getHits(int timestamp) {
        while (!queue.isEmpty() && queue.peek() <= timestamp - 300) queue.poll();
        return queue.size();
    }
    
    public static void main(String[] args) {
        Problem07_HitCounter sol = new Problem07_HitCounter();
        sol.hit(1); sol.hit(2); sol.hit(3);
        System.out.println(sol.getHits(4));   // 3
        sol.hit(300);
        System.out.println(sol.getHits(300)); // 4
        System.out.println(sol.getHits(301)); // 3
    }
}
