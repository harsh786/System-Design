/**
 * Problem 16: Dota2 Senate (LeetCode 649)
 *
 * Greedy Choice: Each senator bans the nearest enemy senator in circular order.
 *
 * Time: O(n), Space: O(n)
 *
 * Production Analogy: Consensus protocol where nodes eliminate opposing votes in round-robin.
 */
import java.util.*;
public class Problem16_Dota2Senate {
    
    public static String predictPartyVictory(String senate) {
        Queue<Integer> radiant = new LinkedList<>(), dire = new LinkedList<>();
        int n = senate.length();
        for (int i = 0; i < n; i++) {
            if (senate.charAt(i) == 'R') radiant.add(i);
            else dire.add(i);
        }
        while (!radiant.isEmpty() && !dire.isEmpty()) {
            int r = radiant.poll(), d = dire.poll();
            if (r < d) radiant.add(r + n);
            else dire.add(d + n);
        }
        return radiant.isEmpty() ? "Dire" : "Radiant";
    }
    
    public static void main(String[] args) {
        System.out.println(predictPartyVictory("RD"));   // Radiant
        System.out.println(predictPartyVictory("RDD"));  // Dire
        System.out.println(predictPartyVictory("RDRD")); // Radiant
    }
}
