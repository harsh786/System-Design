import java.util.*;

public class Problem47_MergeSortWithInsertionCutoff {
    static final int CUTOFF = 7;
    
    static void sort(int[] arr) { mergeSort(arr, 0, arr.length - 1); }
    
    static void mergeSort(int[] a, int lo, int hi) {
        if (hi - lo < CUTOFF) { insertionSort(a, lo, hi); return; }
        int mid = (lo + hi) / 2; mergeSort(a, lo, mid); mergeSort(a, mid + 1, hi);
        if (a[mid] > a[mid + 1]) merge(a, lo, mid, hi);
    }
    
    static void insertionSort(int[] a, int lo, int hi) {
        for (int i = lo + 1; i <= hi; i++) { int k = a[i], j = i - 1; while (j >= lo && a[j] > k) { a[j+1] = a[j]; j--; } a[j+1] = k; }
    }
    
    static void merge(int[] a, int lo, int mid, int hi) {
        int[] t = new int[hi-lo+1]; int i=lo,j=mid+1,k=0;
        while(i<=mid&&j<=hi)t[k++]=a[i]<=a[j]?a[i++]:a[j++];
        while(i<=mid)t[k++]=a[i++];while(j<=hi)t[k++]=a[j++];
        System.arraycopy(t,0,a,lo,t.length);
    }
    
    public static void main(String[] args) {
        int[] arr = new int[20]; Random r = new Random(42); for(int i=0;i<20;i++)arr[i]=r.nextInt(100);
        sort(arr);
        System.out.println(Arrays.toString(arr));
    }
}
