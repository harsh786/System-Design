/**
 * Problem 20: Count of Range Sum (LeetCode 327)
 * Count ranges [i,j] where lower <= sum(nums[i..j]) <= upper
 * 
 * D&C Approach (Merge Sort on prefix sums):
 * - Build prefix sum array. Range sum = prefix[j] - prefix[i]
 * - DIVIDE: Split prefix sum array
 * - CONQUER: Count valid pairs in each half
 * - COMBINE: During merge, for each left prefix[i], count right prefix[j]
 *   where lower <= prefix[j] - prefix[i] <= upper
 * 
 * Time: O(n log n), Space: O(n)
 * 
 * Production Analogy:
 * - Counting transactions within amount range across time-partitioned data
 * - Monitoring metrics within SLA bounds across distributed logs
 */
public class Problem20_CountOfRangeSum {

    public static int countRangeSum(int[] nums, int lower, int upper) {
        int n = nums.length;
        long[] prefix = new long[n + 1];
        for (int i = 0; i < n; i++) prefix[i + 1] = prefix[i] + nums[i];
        return mergeSort(prefix, 0, n, lower, upper);
    }

    private static int mergeSort(long[] prefix, int lo, int hi, int lower, int upper) {
        if (lo >= hi) return 0;
        int mid = lo + (hi - lo) / 2;
        int count = mergeSort(prefix, lo, mid, lower, upper) +
                    mergeSort(prefix, mid + 1, hi, lower, upper);
        
        // Count cross pairs: for each i in [lo,mid], find j in [mid+1,hi]
        // where lower <= prefix[j] - prefix[i] <= upper
        int j1 = mid + 1, j2 = mid + 1;
        for (int i = lo; i <= mid; i++) {
            while (j1 <= hi && prefix[j1] - prefix[i] < lower) j1++;
            while (j2 <= hi && prefix[j2] - prefix[i] <= upper) j2++;
            count += (j2 - j1);
        }
        
        // Standard merge
        long[] temp = new long[hi - lo + 1];
        int i = lo, j = mid + 1, k = 0;
        while (i <= mid && j <= hi) {
            if (prefix[i] <= prefix[j]) temp[k++] = prefix[i++];
            else temp[k++] = prefix[j++];
        }
        while (i <= mid) temp[k++] = prefix[i++];
        while (j <= hi) temp[k++] = prefix[j++];
        System.arraycopy(temp, 0, prefix, lo, temp.length);
        
        return count;
    }

    public static void main(String[] args) {
        System.out.println(countRangeSum(new int[]{-2,5,-1}, -2, 2));  // 3
        System.out.println(countRangeSum(new int[]{0}, 0, 0));          // 1
        System.out.println(countRangeSum(new int[]{1,2,3}, 3, 6));      // 3
        System.out.println(countRangeSum(new int[]{-1,-2,-3}, -6, -1)); // 6
    }
}
