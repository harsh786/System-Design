import java.util.*;

/**
 * Problem 39: Find K Closest Elements (LeetCode 658)
 * 
 * D&C / Binary Search Approach:
 * - DIVIDE: Binary search for the leftmost position of the K-element window
 * - Key insight: if arr[mid] is farther from x than arr[mid+k], shift right
 * - The answer is a contiguous window of size k
 * 
 * Time: O(log(n-k) + k), Space: O(1) excluding output
 * 
 * Production Analogy:
 * - Finding nearest k servers to a user's location
 * - K-nearest-neighbors in recommendation systems
 * - Selecting closest cache nodes in CDN routing
 */
public class Problem39_FindKClosestElements {

    public static List<Integer> findClosestElements(int[] arr, int k, int x) {
        // Binary search for left boundary of window
        int lo = 0, hi = arr.length - k;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            // Compare distances from x: arr[mid] vs arr[mid+k]
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
        System.out.println(findClosestElements(new int[]{1,2,3,4,5}, 4, 6));   // [2,3,4,5]
        System.out.println(findClosestElements(new int[]{1,1,1,10,10,10}, 1, 9)); // [10]
        System.out.println(findClosestElements(new int[]{0,1,2,3,4,5,6,7,8,9}, 5, 5)); // [3,4,5,6,7]
    }
}
