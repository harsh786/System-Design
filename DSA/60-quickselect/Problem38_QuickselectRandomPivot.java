import java.util.*;

public class Problem38_QuickselectRandomPivot {
    private Random rand = new Random();

    public int quickselect(int[] arr, int k) {
        int[] a = arr.clone();
        return select(a, 0, a.length - 1, k);
    }

    private int select(int[] a, int lo, int hi, int k) {
        if (lo == hi) return a[lo];
        int pi = lo + rand.nextInt(hi - lo + 1);
        swap(a, pi, hi);
        int pivot = a[hi], s = lo;
        for (int i = lo; i < hi; i++) if (a[i] < pivot) swap(a, s++, i);
        swap(a, s, hi);
        if (s == k) return a[s];
        return s < k ? select(a, s + 1, hi, k) : select(a, lo, s - 1, k);
    }

    private void swap(int[] a, int i, int j) { int t = a[i]; a[i] = a[j]; a[j] = t; }

    public static void main(String[] args) {
        Problem38_QuickselectRandomPivot sol = new Problem38_QuickselectRandomPivot();
        System.out.println(sol.quickselect(new int[]{9, 8, 7, 6, 5, 4, 3, 2, 1}, 4)); // 5
    }
}
