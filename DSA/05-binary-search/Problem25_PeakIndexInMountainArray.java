/**
 * Problem 25: Peak Index in a Mountain Array
 * 
 * Array strictly increases then strictly decreases. Find the peak index.
 * 
 * Approach: Binary search — if arr[mid] < arr[mid+1] we're on ascending side.
 * 
 * Time: O(log n), Space: O(1)
 * 
 * Production Analogy: Finding the inflection point in user growth metrics
 * where growth rate turns negative — identifying peak adoption.
 */
public class Problem25_PeakIndexInMountainArray {
    public static int peakIndexInMountainArray(int[] arr) {
        int lo = 0, hi = arr.length - 1;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (arr[mid] < arr[mid + 1]) lo = mid + 1;
            else hi = mid;
        }
        return lo;
    }

    public static void main(String[] args) {
        System.out.println(peakIndexInMountainArray(new int[]{0,1,0}));       // 1
        System.out.println(peakIndexInMountainArray(new int[]{0,2,1,0}));     // 1
        System.out.println(peakIndexInMountainArray(new int[]{0,10,5,2}));    // 1
        System.out.println(peakIndexInMountainArray(new int[]{3,5,3,2,0}));   // 1
    }
}
