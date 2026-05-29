import java.util.*;

public class Problem30_MergeSortParallelStep {
    // Demonstrates the concept of parallel merge sort (sequential simulation)
    static void parallelMergeSort(int[] arr) {
        int n = arr.length;
        // Bottom-up with "parallel" levels
        for (int size = 1; size < n; size *= 2) {
            System.out.println("Level: size=" + size + " (could be parallelized)");
            for (int lo = 0; lo < n - size; lo += 2 * size) {
                int mid = lo + size - 1, hi = Math.min(lo + 2 * size - 1, n - 1);
                merge(arr, lo, mid, hi);
            }
        }
    }
    
    static void merge(int[] a, int lo, int mid, int hi) {
        int[] t = new int[hi-lo+1]; int i=lo,j=mid+1,k=0;
        while(i<=mid&&j<=hi)t[k++]=a[i]<=a[j]?a[i++]:a[j++];
        while(i<=mid)t[k++]=a[i++];while(j<=hi)t[k++]=a[j++];
        System.arraycopy(t,0,a,lo,t.length);
    }
    
    public static void main(String[] args) {
        int[] arr = {8, 3, 5, 1, 7, 2, 6, 4};
        parallelMergeSort(arr);
        System.out.println(Arrays.toString(arr));
    }
}
