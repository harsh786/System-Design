import java.util.*;

/**
 * Problem 43: Nuts and Bolts Problem (Lock and Key)
 * Given n nuts and n bolts, match each nut with its corresponding bolt.
 * Cannot compare nut-to-nut or bolt-to-bolt, only nut-to-bolt.
 * 
 * D&C Approach:
 * - DIVIDE: Pick a random bolt, partition nuts around it. Then use matched nut
 *   to partition bolts.
 * - CONQUER: Recursively match smaller/larger groups
 * - COMBINE: Concatenation (like quicksort)
 * 
 * Time: O(n log n) average, O(n^2) worst
 * Space: O(log n) stack
 * 
 * Production Analogy:
 * - Matching requests to handlers without direct comparison between handlers
 * - Database join where comparison only works across tables (hash join variant)
 * - A/B test matching where items from different sets need pairing
 */
public class Problem43_NutsAndBoltsProblem {

    public static void matchPairs(char[] nuts, char[] bolts, int lo, int hi) {
        if (lo >= hi) return;
        
        // Partition nuts using last bolt as pivot
        int pivotIdx = partition(nuts, lo, hi, bolts[hi]);
        // Partition bolts using the matched nut as pivot
        partition(bolts, lo, hi, nuts[pivotIdx]);
        
        // Recurse on both halves
        matchPairs(nuts, bolts, lo, pivotIdx - 1);
        matchPairs(nuts, bolts, pivotIdx + 1, hi);
    }

    private static int partition(char[] arr, int lo, int hi, char pivot) {
        int i = lo;
        int j = lo;
        while (j < hi) {
            if (arr[j] < pivot) {
                swap(arr, i, j);
                i++;
            } else if (arr[j] == pivot) {
                swap(arr, j, hi);
                j--;
            }
            j++;
        }
        swap(arr, i, hi);
        return i;
    }

    private static void swap(char[] arr, int i, int j) {
        char t = arr[i]; arr[i] = arr[j]; arr[j] = t;
    }

    public static void main(String[] args) {
        char[] nuts = {'@', '#', '$', '%', '^', '&'};
        char[] bolts = {'$', '%', '&', '^', '@', '#'};
        matchPairs(nuts, bolts, 0, nuts.length - 1);
        System.out.println("Nuts:  " + Arrays.toString(nuts));
        System.out.println("Bolts: " + Arrays.toString(bolts));
        // Both should be in same order
        
        char[] nuts2 = {'a', 'b', 'c'};
        char[] bolts2 = {'c', 'a', 'b'};
        matchPairs(nuts2, bolts2, 0, 2);
        System.out.println("Nuts:  " + Arrays.toString(nuts2));
        System.out.println("Bolts: " + Arrays.toString(bolts2));
    }
}
