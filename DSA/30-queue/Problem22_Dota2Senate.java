import java.util.*;

public class Problem22_Dota2Senate {
    public static String predictPartyVictory(String senate) {
        Queue<Integer> radiant = new LinkedList<>(), dire = new LinkedList<>();
        int n = senate.length();
        for (int i = 0; i < n; i++) {
            if (senate.charAt(i) == 'R') radiant.offer(i); else dire.offer(i);
        }
        while (!radiant.isEmpty() && !dire.isEmpty()) {
            int r = radiant.poll(), d = dire.poll();
            if (r < d) radiant.offer(r + n); else dire.offer(d + n);
        }
        return radiant.isEmpty() ? "Dire" : "Radiant";
    }
    public static void main(String[] args) {
        System.out.println(predictPartyVictory("RDD")); // Dire
    }
}
