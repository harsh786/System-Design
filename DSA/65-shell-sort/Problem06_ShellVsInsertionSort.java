import java.util.*;

/**
 * Problem 6: Shell Sort vs Insertion Sort Comparison
 * 
 * Key insights:
 * - Insertion sort is O(n^2) but O(n) on nearly sorted data
 * - Shell Sort's early passes create nearly sorted data for the final pass
 * - Shell Sort is essentially a multi-pass optimization of insertion sort
 * - For small arrays (< 50 elements), insertion sort may be faster due to overhead
 * 
 * This comparison shows why Shell Sort wins on larger/random arrays
 * but insertion sort can win on small or nearly-sorted arrays.
 */
public class Problem06_ShellVsInsertionSort {

    static long insertionSortComparisons;
    static long shellSortComparisons;

    public static void insertionSort(int[] arr) {
        insertionSortComparisons = 0;
        for (int i = 1; i < arr.length; i++) {
            int temp = arr[i];
            int j = i;
            while (j > 0) {
                insertionSortComparisons++;
                if (arr[j - 1] > temp) {
                    arr[j] = arr[j - 1];
                    j--;
                } else break;
            }
            arr[j] = temp;
        }
    }

    public static void shellSort(int[] arr) {
        shellSortComparisons = 0;
        int n = arr.length;
        int gap = 1;
        while (gap < n / 3) gap = 3 * gap + 1;
        
        while (gap >= 1) {
            for (int i = gap; i < n; i++) {
                int temp = arr[i];
                int j = i;
                while (j >= gap) {
                    shellSortComparisons++;
                    if (arr[j - gap] > temp) {
                        arr[j] = arr[j - gap];
                        j -= gap;
                    } else break;
                }
                arr[j] = temp;
            }
            gap /= 3;
        }
    }

    public static void main(String[] args) {
        int[] sizes = {100, 1000, 5000, 10000};
        Random rand = new Random(42);

        System.out.println("=== Random Arrays ===");
        System.out.printf("%-8s %-15s %-15s %-15s %-15s%n", 
            "Size", "Insertion(ms)", "Shell(ms)", "Ins.Comps", "Shell.Comps");
        
        for (int n : sizes) {
            int[] original = new int[n];
            for (int i = 0; i < n; i++) original[i] = rand.nextInt(100000);
            
            int[] arr1 = original.clone();
            long t1 = System.nanoTime();
            insertionSort(arr1);
            long time1 = System.nanoTime() - t1;
            long insComps = insertionSortComparisons;

            int[] arr2 = original.clone();
            long t2 = System.nanoTime();
            shellSort(arr2);
            long time2 = System.nanoTime() - t2;
            long shComps = shellSortComparisons;

            System.out.printf("%-8d %-15.2f %-15.2f %-15d %-15d%n",
                n, time1/1e6, time2/1e6, insComps, shComps);
        }

        System.out.println("\n=== Nearly Sorted Arrays (5% displaced) ===");
        for (int n : sizes) {
            int[] original = new int[n];
            for (int i = 0; i < n; i++) original[i] = i;
            // Displace 5%
            for (int i = 0; i < n / 20; i++) {
                int a = rand.nextInt(n), b = rand.nextInt(n);
                int tmp = original[a]; original[a] = original[b]; original[b] = tmp;
            }

            int[] arr1 = original.clone();
            long t1 = System.nanoTime();
            insertionSort(arr1);
            long time1 = System.nanoTime() - t1;

            int[] arr2 = original.clone();
            long t2 = System.nanoTime();
            shellSort(arr2);
            long time2 = System.nanoTime() - t2;

            System.out.printf("n=%-6d Insertion: %.2f ms, Shell: %.2f ms%n",
                n, time1/1e6, time2/1e6);
        }
    }
}
