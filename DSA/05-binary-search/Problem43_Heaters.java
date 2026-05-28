import java.util.Arrays;

/**
 * Problem 43: Heaters
 * 
 * Find minimum radius so every house is covered by at least one heater.
 * 
 * Approach: Sort heaters. For each house, binary search for nearest heater.
 * Answer is max of all minimum distances.
 * 
 * Time: O((m+n) log n), Space: O(1)
 * 
 * Production Analogy: Determining minimum CDN cache radius to ensure every
 * user is within acceptable latency of at least one edge server.
 */
public class Problem43_Heaters {
    public static int findRadius(int[] houses, int[] heaters) {
        Arrays.sort(heaters);
        int maxDist = 0;
        for (int house : houses) {
            int lo = 0, hi = heaters.length - 1;
            // Find closest heater via binary search
            while (lo < hi) {
                int mid = lo + (hi - lo) / 2;
                if (heaters[mid] < house) lo = mid + 1;
                else hi = mid;
            }
            // lo is first heater >= house
            int dist = Math.abs(heaters[lo] - house);
            if (lo > 0) dist = Math.min(dist, Math.abs(heaters[lo - 1] - house));
            maxDist = Math.max(maxDist, dist);
        }
        return maxDist;
    }

    public static void main(String[] args) {
        System.out.println(findRadius(new int[]{1,2,3}, new int[]{2}));        // 1
        System.out.println(findRadius(new int[]{1,2,3,4}, new int[]{1,4}));    // 1
        System.out.println(findRadius(new int[]{1,5}, new int[]{2}));           // 3
    }
}
