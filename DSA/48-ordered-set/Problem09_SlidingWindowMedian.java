import java.util.*;

public class Problem09_SlidingWindowMedian {
    // LC 480: Return median of each sliding window of size k
    public static double[] medianSlidingWindow(int[] nums, int k) {
        TreeMap<Integer, Integer> lo = new TreeMap<>(Collections.reverseOrder());
        TreeMap<Integer, Integer> hi = new TreeMap<>();
        int loSize = 0, hiSize = 0;
        double[] result = new double[nums.length - k + 1];

        for (int i = 0; i < nums.length; i++) {
            // Add to lo
            lo.merge(nums[i], 1, Integer::sum); loSize++;
            // Move top of lo to hi
            int top = lo.firstKey();
            lo.merge(top, -1, Integer::sum); if (lo.getOrDefault(top, 0) == 0) lo.remove(top);
            loSize--;
            hi.merge(top, 1, Integer::sum); hiSize++;
            // Balance
            if (hiSize > loSize) {
                int bot = hi.firstKey();
                hi.merge(bot, -1, Integer::sum); if (hi.getOrDefault(bot, 0) == 0) hi.remove(bot);
                hiSize--;
                lo.merge(bot, 1, Integer::sum); loSize++;
            }
            if (i >= k - 1) {
                if (k % 2 == 1) result[i - k + 1] = lo.firstKey();
                else result[i - k + 1] = ((long) lo.firstKey() + hi.firstKey()) / 2.0;
                int rem = nums[i - k + 1];
                if (lo.containsKey(rem)) { lo.merge(rem, -1, Integer::sum); if (lo.get(rem) == 0) lo.remove(rem); loSize--; }
                else { hi.merge(rem, -1, Integer::sum); if (hi.get(rem) == 0) hi.remove(rem); hiSize--; }
                if (loSize < hiSize) {
                    int bot = hi.firstKey();
                    hi.merge(bot, -1, Integer::sum); if (hi.getOrDefault(bot, 0) == 0) hi.remove(bot);
                    hiSize--;
                    lo.merge(bot, 1, Integer::sum); loSize++;
                } else if (loSize > hiSize + 1) {
                    int t = lo.firstKey();
                    lo.merge(t, -1, Integer::sum); if (lo.getOrDefault(t, 0) == 0) lo.remove(t);
                    loSize--;
                    hi.merge(t, 1, Integer::sum); hiSize++;
                }
            }
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(medianSlidingWindow(new int[]{1,3,-1,-3,5,3,6,7}, 3)));
    }
}
