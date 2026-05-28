import java.util.*;

/**
 * Problem 18: Find K Closest Elements
 * 
 * Given sorted array, find k closest elements to x.
 * 
 * Approach: Binary search for the left boundary of the k-length window.
 * Compare arr[mid] and arr[mid+k] distances to x.
 * 
 * Time: O(log(n-k) + k), Space: O(k) for result
 * 
 * Production Analogy: Finding k nearest data centers to a user's location
 * from a sorted list of positions — sliding window with binary search.
 */
public class Problem18_FindKClosestElements {
    public static List<Integer> findClosestElements(int[] arr, int k, int x) {
        int lo = 0, hi = arr.length - k;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            // If x - arr[mid] > arr[mid+k] - x, left boundary should move right
            if (x - arr[mid] > arr[mid + k] - x) lo = mid + 1;
            else hi = mid;
        }
        List<Integer> result = new ArrayList<>();
        for (int i = lo; i < lo + k; i++) result.add(arr[i]);
        return result;
    }

    public static void main(String[] args) {
        System.out.println(findClosestElements(new int[]{1,2,3,4,5}, 4, 3));   // [1,2,3,4]
        System.out.println(findClosestElements(new int[]{1,2,3,4,5}, 4, -1));  // [1,2,3,4]
        System.out.println(findClosestElements(new int[]{1,1,1,10,10,10}, 1, 9)); // [10]
    }
}
