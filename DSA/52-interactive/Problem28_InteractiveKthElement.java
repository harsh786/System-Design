import java.util.*;

public class Problem28_InteractiveKthElement {
    static int[] arr = {7, 2, 9, 1, 5, 8, 3};
    static int query(int i) { return arr[i]; }
    // Compare two indices
    static int compare(int i, int j) { return Integer.compare(arr[i], arr[j]); }
    
    static int quickselect(int n, int k) {
        int[] indices = new int[n]; for (int i = 0; i < n; i++) indices[i] = i;
        return quickselect(indices, 0, n - 1, k - 1);
    }
    
    static int quickselect(int[] idx, int lo, int hi, int k) {
        if (lo == hi) return query(idx[lo]);
        int pivot = idx[hi], i = lo;
        for (int j = lo; j < hi; j++) {
            if (compare(idx[j], hi) < 0) { int t = idx[i]; idx[i] = idx[j]; idx[j] = t; i++; }
        }
        int t = idx[i]; idx[i] = idx[hi]; idx[hi] = t;
        if (i == k) return query(idx[i]);
        else if (k < i) return quickselect(idx, lo, i - 1, k);
        else return quickselect(idx, i + 1, hi, k);
    }
    
    public static void main(String[] args) {
        System.out.println("3rd smallest: " + quickselect(arr.length, 3)); // 3
    }
}
