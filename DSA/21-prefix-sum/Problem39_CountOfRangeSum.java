/**
 * Problem 39: Count of Range Sum (LeetCode 327)
 * 
 * Pattern: Prefix sums + merge sort to count pairs where lower <= prefix[j]-prefix[i] <= upper
 * 
 * Time: O(n log n), Space: O(n)
 * 
 * Production Analogy: Counting time intervals where cumulative metric change
 * falls within acceptable bounds (SLA compliance windows).
 */
public class Problem39_CountOfRangeSum {

    private static int count;

    public static int countRangeSum(int[] nums, int lower, int upper) {
        int n = nums.length;
        long[] prefix = new long[n + 1];
        for (int i = 0; i < n; i++) prefix[i + 1] = prefix[i] + nums[i];
        count = 0;
        mergeSort(prefix, 0, n, lower, upper);
        return count;
    }

    private static void mergeSort(long[] prefix, int lo, int hi, int lower, int upper) {
        if (lo >= hi) return;
        int mid = lo + (hi - lo) / 2;
        mergeSort(prefix, lo, mid, lower, upper);
        mergeSort(prefix, mid + 1, hi, lower, upper);

        // Count valid pairs
        int j = mid + 1, k = mid + 1;
        for (int i = lo; i <= mid; i++) {
            while (j <= hi && prefix[j] - prefix[i] < lower) j++;
            while (k <= hi && prefix[k] - prefix[i] <= upper) k++;
            count += k - j;
        }

        // Merge
        long[] temp = new long[hi - lo + 1];
        int left = lo, right = mid + 1, idx = 0;
        while (left <= mid && right <= hi)
            temp[idx++] = prefix[left] <= prefix[right] ? prefix[left++] : prefix[right++];
        while (left <= mid) temp[idx++] = prefix[left++];
        while (right <= hi) temp[idx++] = prefix[right++];
        System.arraycopy(temp, 0, prefix, lo, temp.length);
    }

    public static void main(String[] args) {
        assert countRangeSum(new int[]{-2, 5, -1}, -2, 2) == 3;
        assert countRangeSum(new int[]{0}, 0, 0) == 1;
        assert countRangeSum(new int[]{-2147483647, 0, -2147483647, 2147483647}, -564, 3864) == 3;
        System.out.println("All tests passed!");
    }
}
