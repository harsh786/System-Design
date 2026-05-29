import java.util.*;

public class Problem21_DesignHitCounter {
    // O(1) hit, O(1) getHits using buckets
    int[] times = new int[300], hits = new int[300];
    public void hit(int timestamp) {
        int idx = timestamp % 300;
        if (times[idx] != timestamp) { times[idx] = timestamp; hits[idx] = 1; }
        else hits[idx]++;
    }
    public int getHits(int timestamp) {
        int total = 0;
        for (int i = 0; i < 300; i++) if (timestamp - times[i] < 300) total += hits[i];
        return total;
    }
    public static void main(String[] args) {
        Problem21_DesignHitCounter hc = new Problem21_DesignHitCounter();
        hc.hit(1); hc.hit(2); hc.hit(3);
        System.out.println(hc.getHits(4)); // 3
        hc.hit(300);
        System.out.println(hc.getHits(300)); // 4
        System.out.println(hc.getHits(301)); // 3
    }
}
