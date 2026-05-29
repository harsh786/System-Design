import java.util.*;

public class Problem24_RandomizedSelectMedian {
    static Random rand = new Random();

    public static double findMedian(int[] arr) {
        int n = arr.length;
        if (n % 2 == 1) return quickselect(arr.clone(), 0, n-1, n/2);
        else return (quickselect(arr.clone(), 0, n-1, n/2-1) + quickselect(arr.clone(), 0, n-1, n/2)) / 2.0;
    }

    static int quickselect(int[] arr, int lo, int hi, int k) {
        if (lo == hi) return arr[lo];
        int pi = lo + rand.nextInt(hi-lo+1);
        int tmp = arr[pi]; arr[pi] = arr[hi]; arr[hi] = tmp;
        int pivot = arr[hi], i = lo;
        for (int j = lo; j < hi; j++) if (arr[j] <= pivot) { tmp=arr[i];arr[i]=arr[j];arr[j]=tmp;i++; }
        tmp=arr[i];arr[i]=arr[hi];arr[hi]=tmp;
        if (k == i) return arr[i];
        return k < i ? quickselect(arr,lo,i-1,k) : quickselect(arr,i+1,hi,k);
    }

    public static void main(String[] args) {
        System.out.println(findMedian(new int[]{3,1,4,1,5,9})); // 3.5
        System.out.println(findMedian(new int[]{7,2,5})); // 5.0
    }
}
