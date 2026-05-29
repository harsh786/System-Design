import java.util.*;

public class Problem12_CountOfRangeSum {
    int[] bit;
    void update(int i, int n) { for (; i <= n; i += i & (-i)) bit[i]++; }
    int query(int i) { int s = 0; for (; i > 0; i -= i & (-i)) s += bit[i]; return s; }

    public int countRangeSum(int[] nums, int lower, int upper) {
        long[] prefix = new long[nums.length + 1];
        for (int i = 0; i < nums.length; i++) prefix[i + 1] = prefix[i] + nums[i];
        long[] sorted = Arrays.stream(prefix).distinct().sorted().toArray();
        Map<Long, Integer> rank = new HashMap<>();
        for (int i = 0; i < sorted.length; i++) rank.put(sorted[i], i + 1);
        int n = rank.size();
        bit = new int[n + 1];
        int count = 0;
        for (long p : prefix) {
            long lo = p - upper, hi = p - lower;
            int li = lowerBound(sorted, lo), ri = upperBound(sorted, hi);
            if (li <= ri) count += query(ri) - query(li - 1);
            update(rank.get(p), n);
        }
        return count;
    }

    int lowerBound(long[] a, long t) { int lo=0,hi=a.length; while(lo<hi){int m=(lo+hi)/2;if(a[m]<t)lo=m+1;else hi=m;} return lo+1; }
    int upperBound(long[] a, long t) { int lo=0,hi=a.length; while(lo<hi){int m=(lo+hi)/2;if(a[m]<=t)lo=m+1;else hi=m;} return lo; }

    public static void main(String[] args) {
        System.out.println(new Problem12_CountOfRangeSum().countRangeSum(new int[]{-2,5,-1}, -2, 2)); // 3
    }
}
