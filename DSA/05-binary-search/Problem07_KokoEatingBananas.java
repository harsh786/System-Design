/**
 * Problem 7: Koko Eating Bananas
 * 
 * Koko eats bananas at speed k per hour. Find minimum k to finish within h hours.
 * 
 * Approach: Binary search on answer space [1, max(piles)].
 * Invariant: If speed k works, all speeds > k also work (monotonic).
 * 
 * Time: O(n * log(max)), Space: O(1)
 * 
 * Production Analogy: Finding minimum provisioned throughput (RU/s) for a
 * database to process all queued writes within a time window.
 */
public class Problem07_KokoEatingBananas {
    public static int minEatingSpeed(int[] piles, int h) {
        int lo = 1, hi = 0;
        for (int p : piles) hi = Math.max(hi, p);
        
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (canFinish(piles, mid, h)) hi = mid;
            else lo = mid + 1;
        }
        return lo;
    }

    private static boolean canFinish(int[] piles, int speed, int h) {
        long hours = 0;
        for (int p : piles) hours += (p + speed - 1) / speed; // ceil division
        return hours <= h;
    }

    public static void main(String[] args) {
        System.out.println(minEatingSpeed(new int[]{3,6,7,11}, 8));       // 4
        System.out.println(minEatingSpeed(new int[]{30,11,23,4,20}, 5));  // 30
        System.out.println(minEatingSpeed(new int[]{30,11,23,4,20}, 6));  // 23
        System.out.println(minEatingSpeed(new int[]{1}, 1));               // 1
        System.out.println(minEatingSpeed(new int[]{1000000000}, 2));      // 500000000
    }
}
