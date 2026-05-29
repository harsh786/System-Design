/**
 * Problem 1: Shell Sort Implementation
 * 
 * Shell Sort is a generalization of insertion sort that allows exchange of items
 * that are far apart. The idea is to arrange the list of elements so that,
 * starting anywhere, taking every h-th element produces a sorted list (h-sorted).
 * 
 * Algorithm:
 * 1. Start with a large gap, then reduce the gap
 * 2. For each gap, perform a gapped insertion sort
 * 3. When gap = 1, it becomes standard insertion sort (but array is nearly sorted)
 * 
 * Time Complexity: O(n^2) worst case with Shell's original gaps, O(n^(3/2)) with better gaps
 * Space Complexity: O(1)
 */
public class Problem01_ShellSort {

    public static void shellSort(int[] arr) {
        int n = arr.length;
        
        // Start with a big gap, then reduce the gap (Shell's original sequence: n/2, n/4, ..., 1)
        for (int gap = n / 2; gap > 0; gap /= 2) {
            // Do a gapped insertion sort for this gap size
            // The first gap elements arr[0..gap-1] are already in gapped order
            // Keep adding one more element until the entire array is gap sorted
            for (int i = gap; i < n; i++) {
                // Save arr[i] and make a hole at position i
                int temp = arr[i];
                
                // Shift earlier gap-sorted elements up until the correct location for arr[i] is found
                int j;
                for (j = i; j >= gap && arr[j - gap] > temp; j -= gap) {
                    arr[j] = arr[j - gap];
                }
                
                // Put temp (the original arr[i]) in its correct location
                arr[j] = temp;
            }
        }
    }

    public static void main(String[] args) {
        int[] arr = {12, 34, 54, 2, 3, 78, 23, 45, 67, 1};
        
        System.out.println("Original array:");
        printArray(arr);
        
        shellSort(arr);
        
        System.out.println("Sorted array:");
        printArray(arr);
        
        // Verify sorting
        assert isSorted(arr) : "Array is not sorted!";
        System.out.println("Sorting verified: PASS");
    }

    private static void printArray(int[] arr) {
        StringBuilder sb = new StringBuilder("[");
        for (int i = 0; i < arr.length; i++) {
            sb.append(arr[i]);
            if (i < arr.length - 1) sb.append(", ");
        }
        sb.append("]");
        System.out.println(sb.toString());
    }

    private static boolean isSorted(int[] arr) {
        for (int i = 1; i < arr.length; i++) {
            if (arr[i] < arr[i - 1]) return false;
        }
        return true;
    }
}
