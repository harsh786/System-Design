import java.util.*;

public class Problem38_Dota2Senate {
    // 649. Dota2 Senate: R and D senators ban each other. Greedy with queue.
    
    public String predictPartyVictory(String senate) {
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
        Problem38_Dota2Senate sol = new Problem38_Dota2Senate();
        System.out.println(sol.predictPartyVictory("RD"));   // "Radiant"
        System.out.println(sol.predictPartyVictory("RDD"));  // "Dire"
    }
}
