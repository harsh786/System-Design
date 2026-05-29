import java.util.*;
import java.util.concurrent.*;

public class Problem48_ParallelMergeSortForkJoin {
    static class MergeSortTask extends RecursiveAction {
        int[] arr, aux; int lo, hi;
        MergeSortTask(int[] a, int[] aux, int lo, int hi) { arr=a;this.aux=aux;this.lo=lo;this.hi=hi; }
        
        protected void compute() {
            if (hi - lo < 64) { Arrays.sort(arr, lo, hi + 1); return; }
            int mid = (lo + hi) / 2;
            invokeAll(new MergeSortTask(arr, aux, lo, mid), new MergeSortTask(arr, aux, mid + 1, hi));
            merge(arr, aux, lo, mid, hi);
        }
    }
    
    static void merge(int[] a, int[] aux, int lo, int mid, int hi) {
        System.arraycopy(a, lo, aux, lo, hi - lo + 1);
        int i = lo, j = mid + 1;
        for (int k = lo; k <= hi; k++) {
            if (i > mid) a[k] = aux[j++];
            else if (j > hi) a[k] = aux[i++];
            else if (aux[i] <= aux[j]) a[k] = aux[i++];
            else a[k] = aux[j++];
        }
    }
    
    public static void main(String[] args) {
        int[] arr = new int[1000]; Random r = new Random(42); for(int i=0;i<1000;i++)arr[i]=r.nextInt(10000);
        int[] aux = new int[1000];
        ForkJoinPool pool = new ForkJoinPool();
        pool.invoke(new MergeSortTask(arr, aux, 0, arr.length - 1));
        System.out.println("First 20: " + Arrays.toString(Arrays.copyOf(arr, 20)));
        // Verify sorted
        boolean sorted = true; for(int i=1;i<arr.length;i++) if(arr[i]<arr[i-1])sorted=false;
        System.out.println("Sorted: " + sorted);
    }
}
