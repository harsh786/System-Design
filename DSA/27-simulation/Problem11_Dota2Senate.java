/**
 * Problem: Dota2 Senate (LeetCode 649)
 * Approach: Two queues simulation - each senator bans the next opponent
 * Complexity: O(n) time, O(n) space
 * Production Analogy: Priority-based conflict resolution in distributed consensus
 */
import java.util.*;
public class Problem11_Dota2Senate {
    public String predictPartyVictory(String senate) {
        Queue<Integer> r = new LinkedList<>(), d = new LinkedList<>();
        int n = senate.length();
        for (int i = 0; i < n; i++) {
            if (senate.charAt(i)=='R') r.offer(i); else d.offer(i);
        }
        while (!r.isEmpty() && !d.isEmpty()) {
            int ri = r.poll(), di = d.poll();
            if (ri < di) r.offer(ri+n); else d.offer(di+n);
        }
        return r.isEmpty() ? "Dire" : "Radiant";
    }
    public static void main(String[] args) {
        System.out.println(new Problem11_Dota2Senate().predictPartyVictory("RDD")); // Dire
    }
}
