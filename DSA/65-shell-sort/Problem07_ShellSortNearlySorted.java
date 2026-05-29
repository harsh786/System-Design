import java.util.*;

/**
 * Problem 7: Shell Sort for Nearly Sorted Arrays
 * 
 * Nearly sorted arrays are common in practice:
 * - Streaming data with slight delays
 * - Re-sorting after small modifications
 * - Data with natural ordering + noise
 * 
 * For k-sorted arrays (each element is at most k positions from its final position),
 * Shell Sort with appropriate gaps can sort in O(n*k) or better.
 * 
 * Adaptive approach: detect "sortedness" and choose gaps accordingly.
 */
public class Problem07_ShellSortNearlySorted {

    /**
     * Measure how sorted an array is: count inversions (approximation)
     * Returns ratio of actual inversions to max possible inversions
     */
    public static double measureDisorder(int[] arr) {
        long inversions = 0;
        int n = arr.length;
        // Sample-based approximation for large arrays
        int samples = Math.min(n, 1000);
        Random rand = new Random(0);
        for (int s = 0; s < samples; s++) {
            int i = rand.nextInt(n - 1);
            for (int j = i + 1; j < Math.min(i + 50, n); j++) {
                if (arr[i] > arr[j]) inversions++;
            }
        }
        return (double) inversions / (samples * 25); // Normalized estimate
    }

    /**
     * Adaptive Shell Sort: uses fewer/smaller gaps for nearly sorted arrays
     */
    public static void adaptiveShellSort(int[] arr) {
        int n = arr.length;
        double disorder = measureDisorder(arr);
        
        if (disorder < 0.05) {
            // Very nearly sorted: just use gap=1 (insertion sort)
            gappedInsertionSort(arr, 1);
        } else if (disorder < 0.3) {
            // Somewhat sorted: use small gaps only
            int[] gaps = {5, 3, 1};
            for (int gap : gaps) {
                if (gap < n) gappedInsertionSort(arr, gap);
            }
        } else {
            // Random: use full Knuth sequence
            int gap = 1;
            while (gap < n / 3) gap = 3 * gap + 1;
            while (gap >= 1) {
                gappedInsertionSort(arr, gap);
                gap /= 3;
            }
        }
    }

    private static void gappedInsertionSort(int[] arr, int gap) {
        for (int i = gap; i < arr.length; i++) {
            int temp = arr[i];
            int j = i;
            while (j >= gap && arr[j - gap] > temp) {
                arr[j] = arr[j - gap];
                j -= gap;
            }
            arr[j] = temp;
        }
    }

    /**
     * Generate k-sorted array: each element at most k positions from sorted position
     */
    public static int[] generateKSorted(int n, int k) {
        int[] arr = new int[n];
        for (int i = 0; i < n; i++) arr[i] = i;
        Random rand = new Random(42);
        for (int i = 0; i < n; i++) {
            int j = Math.min(n - 1, i + rand.nextInt(k + 1));
            int tmp = arr[i]; arr[i] = arr[j]; arr[j] = tmp;
        }
        return arr;
    }

    public static void main(String[] args) {
        int n = 10000;
        int[] kValues = {2, 5, 10, 50, 100};
        
        System.out.println("Performance on k-sorted arrays (n=" + n + "):");
        System.out.printf("%-6s %-15s %-15s%n", "k", "Standard(ms)", "Adaptive(ms)");
        
        for (int k : kValues) {
            int[] arr1 = generateKSorted(n, k);
            int[] arr2 = arr1.clone();
            
            // Standard shell sort
            long t1 = System.nanoTime();
            int gap = 1;
            while (gap < n / 3) gap = 3 * gap + 1;
            while (gap >= 1) { gappedInsertionSort(arr1, gap); gap /= 3; }
            long time1 = System.nanoTime() - t1;
            
            // Adaptive
            long t2 = System.nanoTime();
            adaptiveShellSort(arr2);
            long time2 = System.nanoTime() - t2;
            
            // Verify
            for (int i = 1; i < n; i++) assert arr2[i] >= arr2[i-1];
            
            System.out.printf("%-6d %-15.2f %-15.2f%n", k, time1/1e6, time2/1e6);
        }
    }
}
