import java.util.*;

public class Problem42_MultiPivotQuickselect {
    /* Dual-pivot quickselect */
    public int dualPivotSelect(int[] arr, int k) {
        int[] a = arr.clone();
        return select(a, 0, a.length - 1, k);
    }

    private int select(int[] a, int lo, int hi, int k) {
        if (lo >= hi) return a[lo];
        if (a[lo] > a[hi]) swap(a, lo, hi);
        int p = a[lo], q = a[hi];
        int lt = lo + 1, gt = hi - 1, i = lo + 1;
        while (i <= gt) {
            if (a[i] < p) { swap(a, i, lt); lt++; i++; }
            else if (a[i] > q) { swap(a, i, gt); gt--; }
            else i++;
        }
        swap(a, lo, --lt); swap(a, hi, ++gt);
        if (k <= lt) return select(a, lo, lt, k);
        else if (k >= gt) return select(a, gt, hi, k);
        else return select(a, lt + 1, gt - 1, k);
    }

    private void swap(int[] a, int i, int j) { int t = a[i]; a[i] = a[j]; a[j] = t; }

    public static void main(String[] args) {
        Problem42_MultiPivotQuickselect sol = new Problem42_MultiPivotQuickselect();
        System.out.println(sol.dualPivotSelect(new int[]{9, 1, 5, 3, 7, 2, 8, 4, 6}, 4)); // 5
    }
}
