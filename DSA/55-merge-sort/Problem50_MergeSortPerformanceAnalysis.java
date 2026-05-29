import java.util.*;

public class Problem50_MergeSortPerformanceAnalysis {
    static long comparisons, arrayAccesses;
    
    static void sort(int[] arr) { comparisons=0; arrayAccesses=0; mergeSort(arr, 0, arr.length-1); }
    
    static void mergeSort(int[] a, int lo, int hi) {
        if (lo >= hi) return;
        int mid = (lo+hi)/2; mergeSort(a,lo,mid); mergeSort(a,mid+1,hi);
        int[] t=new int[hi-lo+1]; int i=lo,j=mid+1,k=0;
        while(i<=mid&&j<=hi){comparisons++;arrayAccesses+=2;t[k++]=a[i]<=a[j]?a[i++]:a[j++];}
        while(i<=mid){arrayAccesses++;t[k++]=a[i++];}
        while(j<=hi){arrayAccesses++;t[k++]=a[j++];}
        arrayAccesses+=t.length;
        System.arraycopy(t,0,a,lo,t.length);
    }
    
    public static void main(String[] args) {
        for (int n : new int[]{100, 1000, 10000}) {
            int[] arr = new int[n]; Random r=new Random(42); for(int i=0;i<n;i++)arr[i]=r.nextInt(n);
            sort(arr);
            double nlogn = n * Math.log(n) / Math.log(2);
            System.out.printf("n=%5d: comparisons=%7d (n*logn=%.0f) accesses=%8d%n", n, comparisons, nlogn, arrayAccesses);
        }
    }
}
