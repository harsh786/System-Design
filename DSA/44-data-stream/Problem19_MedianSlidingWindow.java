import java.util.*;

public class Problem19_MedianSlidingWindow {
    // 480. Sliding Window Median using two TreeMaps (multisets).
    
    public double[] medianSlidingWindow(int[] nums, int k) {
        TreeMap<int[], Integer> lo = new TreeMap<>((a,b) -> a[0] != b[0] ? a[0]-b[0] : a[1]-b[1]);
        TreeMap<int[], Integer> hi = new TreeMap<>((a,b) -> a[0] != b[0] ? a[0]-b[0] : a[1]-b[1]);
        // Simpler: use two multiset-like structures
        // Using sorted set with index for uniqueness
        TreeSet<long[]> small = new TreeSet<>((a,b) -> a[0]!=b[0] ? Long.compare(a[0],b[0]) : Long.compare(a[1],b[1]));
        TreeSet<long[]> large = new TreeSet<>((a,b) -> a[0]!=b[0] ? Long.compare(a[0],b[0]) : Long.compare(a[1],b[1]));
        
        double[] res = new double[nums.length - k + 1];
        for (int i = 0; i < nums.length; i++) {
            small.add(new long[]{nums[i], i});
            large.add(small.pollLast());
            if (large.size() > small.size()) small.add(large.pollFirst());
            
            if (small.size() + large.size() == k) {
                if (k % 2 == 1) res[i-k+1] = small.last()[0];
                else res[i-k+1] = (small.last()[0] + large.first()[0]) / 2.0;
                // Remove element going out
                long[] toRemove = new long[]{nums[i-k+1], i-k+1};
                if (!small.remove(toRemove)) large.remove(toRemove);
                // Rebalance
                if (small.size() < large.size()) small.add(large.pollFirst());
                else if (small.size() > large.size() + 1) large.add(small.pollLast());
            }
        }
        return res;
    }
    
    public static void main(String[] args) {
        Problem19_MedianSlidingWindow sol = new Problem19_MedianSlidingWindow();
        System.out.println(Arrays.toString(sol.medianSlidingWindow(new int[]{1,3,-1,-3,5,3,6,7}, 3)));
    }
}
