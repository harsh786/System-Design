import java.util.*;

public class Problem29_Dota2Senate {
    // LC 649
    static String predictPartyVictory(String senate) {
        Queue<Integer> radiant = new LinkedList<>(), dire = new LinkedList<>();
        int n = senate.length();
        for (int i = 0; i < n; i++) {
            if (senate.charAt(i) == 'R') radiant.add(i); else dire.add(i);
        }
        while (!radiant.isEmpty() && !dire.isEmpty()) {
            int r = radiant.poll(), d = dire.poll();
            if (r < d) radiant.add(r + n); else dire.add(d + n);
        }
        return radiant.isEmpty() ? "Dire" : "Radiant";
    }
    
    public static void main(String[] args) {
        System.out.println(predictPartyVictory("RDD")); // Dire
        System.out.println(predictPartyVictory("RD")); // Radiant
    }
}
