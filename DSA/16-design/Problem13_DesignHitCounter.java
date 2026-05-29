import java.util.*;

/**
 * Problem 13: Design Hit Counter
 * 
 * API Contract:
 * - hit(timestamp): Record a hit at given timestamp
 * - getHits(timestamp): Return hits in past 300 seconds
 * 
 * Complexity: hit O(1), getHits O(1) with circular buffer approach
 * Data Structure: Circular array of size 300 with timestamps + counts
 * 
 * Production Analogy: API rate limiting counters, website analytics,
 * health check monitoring, QPS (queries per second) dashboards
 */
public class Problem13_DesignHitCounter {

    static class HitCounter {
        private int[] times;
        private int[] hits;

        public HitCounter() {
            times = new int[300];
            hits = new int[300];
        }

        public void hit(int timestamp) {
            int idx = timestamp % 300;
            if (times[idx] != timestamp) {
                times[idx] = timestamp;
                hits[idx] = 1;
            } else {
                hits[idx]++;
            }
        }

        public int getHits(int timestamp) {
            int total = 0;
            for (int i = 0; i < 300; i++) {
                if (timestamp - times[i] < 300) total += hits[i];
            }
            return total;
        }
    }

    public static void main(String[] args) {
        HitCounter hc = new HitCounter();
        hc.hit(1);
        hc.hit(2);
        hc.hit(3);
        assert hc.getHits(4) == 3;
        hc.hit(300);
        assert hc.getHits(300) == 4;
        assert hc.getHits(301) == 3; // hit at t=1 expired

        // Edge: multiple hits same timestamp
        HitCounter hc2 = new HitCounter();
        hc2.hit(1); hc2.hit(1); hc2.hit(1);
        assert hc2.getHits(1) == 3;

        System.out.println("All tests passed!");
    }
}
