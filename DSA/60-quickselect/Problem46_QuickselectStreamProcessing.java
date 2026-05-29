import java.util.*;

public class Problem46_QuickselectStreamProcessing {
    /* Maintain a sliding window and find kth element using quickselect */
    public int[] kthInWindows(int[] stream, int windowSize, int k) {
        int n = stream.length;
        int[] result = new int[n - windowSize + 1];
        for (int i = 0; i <= n - windowSize; i++) {
            int[] window = Arrays.copyOfRange(stream, i, i + windowSize);
            result[i] = quickselect(window, 0, window.length - 1, k - 1);
        }
        return result;
    }

    private int quickselect(int[] a, int lo, int hi, int k) {
        if (lo == hi) return a[lo];
        int pi = partition(a, lo, hi);
        if (pi == k) return a[pi];
        return pi < k ? quickselect(a, pi + 1, hi, k) : quickselect(a, lo, pi - 1, k);
    }

    private int partition(int[] a, int lo, int hi) {
        int pivot = a[hi], s = lo;
        for (int i = lo; i < hi; i++) if (a[i] < pivot) { int t = a[s]; a[s] = a[i]; a[i] = t; s++; }
        int t = a[s]; a[s] = a[hi]; a[hi] = t; return s;
    }

    public static void main(String[] args) {
        Problem46_QuickselectStreamProcessing sol = new Problem46_QuickselectStreamProcessing();
        System.out.println(Arrays.toString(sol.kthInWindows(new int[]{1,3,5,2,8,4,7}, 3, 2)));
    }
}
