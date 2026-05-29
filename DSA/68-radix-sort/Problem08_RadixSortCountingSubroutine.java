import java.util.*;

/**
 * Problem 8: Radix Sort with Counting Sort Subroutine
 * 
 * Deep dive into the counting sort subroutine and why stability is essential.
 * 
 * Counting Sort:
 * 1. Count occurrences of each key
 * 2. Compute prefix sums (cumulative counts = positions)
 * 3. Place elements at their computed positions (right-to-left for stability)
 * 
 * Stability proof: Elements with equal keys maintain relative order because
 * we traverse right-to-left and decrement positions, so later elements
 * (in original) get earlier positions among equals.
 * 
 * Without stability, LSD radix sort would be INCORRECT.
 */
public class Problem08_RadixSortCountingSubroutine {

    /**
     * Generic counting sort that can sort by any key function.
     * @param arr input array
     * @param keyFunc extracts sort key (0 to maxKey-1) from element
     * @param maxKey number of possible key values
     * @return sorted array (stable)
     */
    public static int[] countingSort(int[] arr, java.util.function.IntUnaryOperator keyFunc, int maxKey) {
        int n = arr.length;
        int[] count = new int[maxKey + 1];
        int[] output = new int[n];
        
        // Step 1: Count frequencies
        for (int v : arr) {
            count[keyFunc.applyAsInt(v)]++;
        }
        
        // Step 2: Prefix sums (convert counts to positions)
        // count[i] = number of elements with key < i (starting position for key i)
        for (int i = 1; i <= maxKey; i++) {
            count[i] += count[i - 1];
        }
        
        // Step 3: Place elements (RIGHT TO LEFT for stability)
        for (int i = n - 1; i >= 0; i--) {
            int key = keyFunc.applyAsInt(arr[i]);
            output[count[key] - 1] = arr[i];
            count[key]--;
        }
        
        return output;
    }

    /**
     * LSD Radix Sort using the generic counting sort
     */
    public static void radixSort(int[] arr) {
        if (arr.length == 0) return;
        int max = 0;
        for (int v : arr) max = Math.max(max, v);
        
        for (int exp = 1; max / exp > 0; exp *= 10) {
            final int e = exp;
            int[] sorted = countingSort(arr, v -> (v / e) % 10, 9);
            System.arraycopy(sorted, 0, arr, 0, arr.length);
        }
    }

    /**
     * Demonstrate why stability matters with a trace
     */
    public static void demonstrateStability() {
        System.out.println("=== Stability Demonstration ===");
        int[] arr = {170, 45, 75, 90, 2, 802, 24, 66};
        System.out.println("Original: " + Arrays.toString(arr));
        
        int max = 802;
        for (int exp = 1; max / exp > 0; exp *= 10) {
            final int e = exp;
            System.out.printf("\nSorting by %d's place:%n", exp);
            // Show keys
            System.out.print("  Keys: [");
            for (int i = 0; i < arr.length; i++) {
                System.out.print((arr[i]/e)%10 + (i<arr.length-1?", ":""));
            }
            System.out.println("]");
            
            arr = countingSort(arr, v -> (v / e) % 10, 9);
            System.out.println("  Result: " + Arrays.toString(arr));
        }
    }

    public static void main(String[] args) {
        demonstrateStability();
        
        System.out.println("\n=== Full Radix Sort ===");
        int[] arr = {329, 457, 657, 839, 436, 720, 355};
        System.out.println("Input:  " + Arrays.toString(arr));
        radixSort(arr);
        System.out.println("Output: " + Arrays.toString(arr));
        
        for (int i = 1; i < arr.length; i++) assert arr[i] >= arr[i-1];
        System.out.println("PASS");
    }
}
