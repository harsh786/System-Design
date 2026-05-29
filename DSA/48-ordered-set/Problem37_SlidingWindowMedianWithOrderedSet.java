import java.util.*;

public class Problem37_SlidingWindowMedianWithOrderedSet {
    // LC 480 with explicit two-TreeMap approach
    public static double[] medianSlidingWindow(int[] nums, int k) {
        Comparator<int[]> cmp = (a, b) -> a[0] != b[0] ? Integer.compare(a[0], b[0]) : Integer.compare(a[1], b[1]);
        TreeSet<int[]> lo = new TreeSet<>(cmp.reversed());
        TreeSet<int[]> hi = new TreeSet<>(cmp);
        double[] res = new double[nums.length - k + 1];

        for (int i = 0; i < nums.length; i++) {
            lo.add(new int[]{nums[i], i});
            hi.add(lo.pollFirst());
            if (hi.size() > lo.size()) lo.add(hi.pollFirst());
            if (i >= k - 1) {
                res[i - k + 1] = k % 2 == 1 ? lo.first()[0] : ((long)lo.first()[0] + hi.first()[0]) / 2.0;
                int[] rem = new int[]{nums[i - k + 1], i - k + 1};
                if (!lo.remove(rem)) hi.remove(rem);
                if (lo.size() < hi.size()) lo.add(hi.pollFirst());
                else if (lo.size() > hi.size() + 1) hi.add(lo.pollFirst());
            }
        }
        return res;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(medianSlidingWindow(new int[]{1,3,-1,-3,5,3,6,7}, 3)));
    }
}
