import java.util.Arrays;

/**
 * Problem 1: Merge Sort
 * 
 * Divide and Conquer approach:
 * - DIVIDE: Split array into two halves
 * - CONQUER: Recursively sort each half
 * - COMBINE: Merge two sorted halves into one sorted array
 * 
 * Recurrence: T(n) = 2T(n/2) + O(n)
 * Time Complexity: O(n log n) - guaranteed for all cases
 * Space Complexity: O(n) - for temporary merge array
 * 
 * Production Analogy:
 * - MapReduce: Map phase splits data across nodes, Reduce phase merges sorted chunks
 * - External sort in databases (e.g., PostgreSQL sorts large result sets this way)
 * - Git merge operations conceptually similar - merge two branches of changes
 */
public class Problem01_MergeSort {

    public static void mergeSort(int[] arr, int left, int right) {
        if (left >= right) return; // Base case: single element is already sorted
        
        int mid = left + (right - left) / 2; // Avoid overflow vs (left+right)/2
        
        // DIVIDE & CONQUER
        mergeSort(arr, left, mid);
        mergeSort(arr, mid + 1, right);
        
        // COMBINE
        merge(arr, left, mid, right);
    }

    private static void merge(int[] arr, int left, int mid, int right) {
        int[] temp = new int[right - left + 1];
        int i = left, j = mid + 1, k = 0;
        
        while (i <= mid && j <= right) {
            if (arr[i] <= arr[j]) {
                temp[k++] = arr[i++];
            } else {
                temp[k++] = arr[j++];
            }
        }
        while (i <= mid) temp[k++] = arr[i++];
        while (j <= right) temp[k++] = arr[j++];
        
        System.arraycopy(temp, 0, arr, left, temp.length);
    }

    public static void main(String[] args) {
        // Test 1: Normal array
        int[] arr1 = {38, 27, 43, 3, 9, 82, 10};
        mergeSort(arr1, 0, arr1.length - 1);
        System.out.println("Test 1: " + Arrays.toString(arr1));

        // Test 2: Already sorted
        int[] arr2 = {1, 2, 3, 4, 5};
        mergeSort(arr2, 0, arr2.length - 1);
        System.out.println("Test 2: " + Arrays.toString(arr2));

        // Test 3: Reverse sorted
        int[] arr3 = {5, 4, 3, 2, 1};
        mergeSort(arr3, 0, arr3.length - 1);
        System.out.println("Test 3: " + Arrays.toString(arr3));

        // Test 4: Single element
        int[] arr4 = {1};
        mergeSort(arr4, 0, arr4.length - 1);
        System.out.println("Test 4: " + Arrays.toString(arr4));

        // Test 5: Duplicates
        int[] arr5 = {3, 1, 4, 1, 5, 9, 2, 6, 5};
        mergeSort(arr5, 0, arr5.length - 1);
        System.out.println("Test 5: " + Arrays.toString(arr5));
    }
}
