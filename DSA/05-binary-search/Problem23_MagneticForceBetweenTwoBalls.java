import java.util.Arrays;

/**
 * Problem 23: Magnetic Force Between Two Balls
 * 
 * Same as aggressive cows — maximize minimum distance between m balls in positions.
 * 
 * Time: O(n log n + n * log(range)), Space: O(1)
 * 
 * Production Analogy: Spreading CDN edge nodes to maximize minimum coverage gap.
 */
public class Problem23_MagneticForceBetweenTwoBalls {
    public static int maxDistance(int[] position, int m) {
        Arrays.sort(position);
        int lo = 1, hi = position[position.length - 1] - position[0];
        while (lo < hi) {
            int mid = lo + (hi - lo + 1) / 2;
            if (canPlace(position, mid, m)) lo = mid;
            else hi = mid - 1;
        }
        return lo;
    }

    private static boolean canPlace(int[] pos, int minDist, int m) {
        int count = 1, last = pos[0];
        for (int i = 1; i < pos.length; i++) {
            if (pos[i] - last >= minDist) { count++; last = pos[i]; }
        }
        return count >= m;
    }

    public static void main(String[] args) {
        System.out.println(maxDistance(new int[]{1,2,3,4,7}, 3));   // 3
        System.out.println(maxDistance(new int[]{5,4,3,2,1,1000000000}, 2)); // 999999999
    }
}
