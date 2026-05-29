import java.util.*;

public class Problem18_DesignHitCounter {
    // O(1) space Hit Counter using circular buffer.
    
    int[] times = new int[300];
    int[] hits = new int[300];
    
    public void hit(int timestamp) {
        int idx = timestamp % 300;
        if (times[idx] != timestamp) { times[idx] = timestamp; hits[idx] = 1; }
        else hits[idx]++;
    }
    
    public int getHits(int timestamp) {
        int total = 0;
        for (int i = 0; i < 300; i++) {
            if (timestamp - times[i] < 300) total += hits[i];
        }
        return total;
    }
    
    public static void main(String[] args) {
        Problem18_DesignHitCounter sol = new Problem18_DesignHitCounter();
        sol.hit(1); sol.hit(2); sol.hit(3);
        System.out.println(sol.getHits(4));   // 3
        sol.hit(300);
        System.out.println(sol.getHits(300)); // 4
        System.out.println(sol.getHits(301)); // 3
    }
}
