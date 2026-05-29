import java.util.*;
public class Problem23_SeparateNegativePositive {
    public void separate(int[] arr) { int lo=0,hi=arr.length-1; while(lo<hi){while(lo<hi&&arr[lo]<0) lo++; while(lo<hi&&arr[hi]>=0) hi--; if(lo<hi){int t=arr[lo];arr[lo]=arr[hi];arr[hi]=t;lo++;hi--;}} }
    public static void main(String[] args){ int[] a={-1,2,-3,4,5,-6,7,-8}; new Problem23_SeparateNegativePositive().separate(a); System.out.println(Arrays.toString(a)); }
}
