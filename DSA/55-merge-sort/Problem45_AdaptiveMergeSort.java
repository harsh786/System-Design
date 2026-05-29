import java.util.*;

public class Problem45_AdaptiveMergeSort {
    // Skip merge if already sorted (optimization)
    static void sort(int[] arr) { mergeSort(arr, 0, arr.length - 1); }
    
    static void mergeSort(int[] a, int lo, int hi) {
        if (lo >= hi) return;
        int mid = (lo + hi) / 2; mergeSort(a, lo, mid); mergeSort(a, mid + 1, hi);
        if (a[mid] <= a[mid + 1]) return; // Already sorted - skip merge
        merge(a, lo, mid, hi);
    }
    
    static void merge(int[] a, int lo, int mid, int hi) {
        int[] t = new int[hi-lo+1]; int i=lo,j=mid+1,k=0;
        while(i<=mid&&j<=hi) t[k++]=a[i]<=a[j]?a[i++]:a[j++];
        while(i<=mid)t[k++]=a[i++]; while(j<=hi)t[k++]=a[j++];
        System.arraycopy(t,0,a,lo,t.length);
    }
    
    public static void main(String[] args) {
        int[] arr = {1, 2, 3, 7, 5, 6, 8, 4}; // partially sorted
        sort(arr);
        System.out.println(Arrays.toString(arr));
    }
}
