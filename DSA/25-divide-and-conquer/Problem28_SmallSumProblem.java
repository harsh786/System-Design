/**
 * Problem 28: Small Sum Problem
 * For each element, sum all elements to its left that are smaller than it.
 * Total small sum = sum of all such values.
 * 
 * D&C Approach (Modified Merge Sort):
 * - DIVIDE: Split array into halves
 * - CONQUER: Count small sums within each half
 * - COMBINE: During merge, when left[i] < right[j], left[i] contributes to
 *   all remaining right elements (mid+1-j+1... wait: right elements from j to hi)
 * 
 * Time: O(n log n), Space: O(n)
 * 
 * Production Analogy:
 * - Computing cumulative contribution metrics in analytics
 * - Aggregating "how many times was this value a minimum" across partitions
 */
public class Problem28_SmallSumProblem {

    public static long smallSum(int[] arr) {
        if (arr.length <= 1) return 0;
        int[] temp = new int[arr.length];
        return mergeSort(arr, temp, 0, arr.length - 1);
    }

    private static long mergeSort(int[] arr, int[] temp, int lo, int hi) {
        if (lo >= hi) return 0;
        int mid = lo + (hi - lo) / 2;
        long sum = 0;
        sum += mergeSort(arr, temp, lo, mid);
        sum += mergeSort(arr, temp, mid + 1, hi);
        sum += merge(arr, temp, lo, mid, hi);
        return sum;
    }

    private static long merge(int[] arr, int[] temp, int lo, int mid, int hi) {
        int i = lo, j = mid + 1, k = lo;
        long sum = 0;
        while (i <= mid && j <= hi) {
            if (arr[i] < arr[j]) {
                // arr[i] is smaller than arr[j]..arr[hi], contributes arr[i] * (hi-j+1) times
                sum += (long) arr[i] * (hi - j + 1);
                temp[k++] = arr[i++];
            } else {
                temp[k++] = arr[j++];
            }
        }
        while (i <= mid) temp[k++] = arr[i++];
        while (j <= hi) temp[k++] = arr[j++];
        System.arraycopy(temp, lo, arr, lo, hi - lo + 1);
        return sum;
    }

    public static void main(String[] args) {
        // [1,3,4,2,5]: 1<3(1), 1<4(1), 3<4(3), 1<2(1), 3<5(3), 4<5(4), 2<5(2), 1<5(1) = 1+1+3+1+3+4+2+1=16
        System.out.println(smallSum(new int[]{1, 3, 4, 2, 5})); // 16
        System.out.println(smallSum(new int[]{1, 2, 3}));        // 1+1+2=4? -> 1(for2)+1+2(for3)=4? No: 1<2:1, 1<3:1, 2<3:2 = 4
        System.out.println(smallSum(new int[]{3, 2, 1}));        // 0
        System.out.println(smallSum(new int[]{5}));              // 0
    }
}
