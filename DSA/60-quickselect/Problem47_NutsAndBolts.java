import java.util.*;

public class Problem47_NutsAndBolts {
    /* Match nuts and bolts using partition */
    public void matchPairs(char[] nuts, char[] bolts, int lo, int hi) {
        if (lo >= hi) return;
        int pivotIdx = partition(nuts, lo, hi, bolts[hi]);
        partition(bolts, lo, hi, nuts[pivotIdx]);
        matchPairs(nuts, bolts, lo, pivotIdx - 1);
        matchPairs(nuts, bolts, pivotIdx + 1, hi);
    }

    private int partition(char[] arr, int lo, int hi, char pivot) {
        int i = lo, j = lo;
        while (j < hi) {
            if (arr[j] < pivot) { swap(arr, i, j); i++; }
            else if (arr[j] == pivot) { swap(arr, j, hi); j--; }
            j++;
        }
        swap(arr, i, hi);
        return i;
    }

    private void swap(char[] a, int i, int j) { char t = a[i]; a[i] = a[j]; a[j] = t; }

    public static void main(String[] args) {
        Problem47_NutsAndBolts sol = new Problem47_NutsAndBolts();
        char[] nuts = {'@', '#', '$', '%', '^', '&'};
        char[] bolts = {'$', '%', '&', '^', '@', '#'};
        sol.matchPairs(nuts, bolts, 0, nuts.length - 1);
        System.out.println("Nuts:  " + Arrays.toString(nuts));
        System.out.println("Bolts: " + Arrays.toString(bolts));
    }
}
