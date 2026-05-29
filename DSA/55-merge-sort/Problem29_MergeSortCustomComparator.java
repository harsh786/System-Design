import java.util.*;

public class Problem29_MergeSortCustomComparator {
    static <T> void mergeSort(T[] arr, Comparator<T> cmp) { sort(arr, 0, arr.length - 1, cmp); }
    
    @SuppressWarnings("unchecked")
    static <T> void sort(T[] a, int lo, int hi, Comparator<T> cmp) {
        if (lo >= hi) return;
        int mid = (lo + hi) / 2; sort(a, lo, mid, cmp); sort(a, mid + 1, hi, cmp);
        Object[] tmp = new Object[hi - lo + 1]; int i = lo, j = mid + 1, k = 0;
        while (i <= mid && j <= hi) tmp[k++] = cmp.compare(a[i], a[j]) <= 0 ? a[i++] : a[j++];
        while (i <= mid) tmp[k++] = a[i++]; while (j <= hi) tmp[k++] = a[j++];
        System.arraycopy(tmp, 0, a, lo, tmp.length);
    }
    
    public static void main(String[] args) {
        String[] arr = {"banana", "apple", "cherry", "date"};
        mergeSort(arr, Comparator.comparingInt(String::length));
        System.out.println(Arrays.toString(arr)); // sorted by length
    }
}
