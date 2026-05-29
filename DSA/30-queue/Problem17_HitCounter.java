import java.util.*;

public class Problem17_HitCounter {
    Queue<Integer> q = new LinkedList<>();
    public void hit(int timestamp) { q.offer(timestamp); }
    public int getHits(int timestamp) {
        while (!q.isEmpty() && q.peek() <= timestamp - 300) q.poll();
        return q.size();
    }
    public static void main(String[] args) {
        Problem17_HitCounter hc = new Problem17_HitCounter();
        hc.hit(1); hc.hit(2); hc.hit(3);
        System.out.println(hc.getHits(4));   // 3
        hc.hit(300);
        System.out.println(hc.getHits(300)); // 4
        System.out.println(hc.getHits(301)); // 3
    }
}
