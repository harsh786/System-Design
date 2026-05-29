import java.util.*;

public class Problem03_ReversePairs {
    int[] bit;

    void update(int i, int n) { for (; i <= n; i += i & (-i)) bit[i]++; }
    int query(int i) { int s = 0; for (; i > 0; i -= i & (-i)) s += bit[i]; return s; }

    public int reversePairs(int[] nums) {
        long[] sorted = Arrays.stream(nums).mapToLong(x -> x).sorted().distinct().toArray();
        int n = sorted.length;
        bit = new int[n + 2];
        int count = 0;
        for (int val : nums) {
            int idx = lowerBound(sorted, 2L * val + 1);
            count += query(n) - query(idx);
            int r = lowerBound(sorted, val) + 1;
            update(r, n);
        }
        return count;
    }

    int lowerBound(long[] arr, long target) {
        int lo = 0, hi = arr.length;
        while (lo < hi) { int mid = (lo + hi) / 2; if (arr[mid] < target) lo = mid + 1; else hi = mid; }
        return lo;
    }

    public static void main(String[] args) {
        System.out.println(new Problem03_ReversePairs().reversePairs(new int[]{1, 3, 2, 3, 1})); // 2
    }
}
