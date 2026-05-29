import java.util.*;
public class Problem22_SortZerosOnes {
    public void sort(int[] arr) { int lo=0,hi=arr.length-1; while(lo<hi){while(lo<hi&&arr[lo]==0) lo++; while(lo<hi&&arr[hi]==1) hi--; if(lo<hi){arr[lo]=0;arr[hi]=1;lo++;hi--;}} }
    public static void main(String[] args){ int[] a={1,0,1,0,0,1,1,0}; new Problem22_SortZerosOnes().sort(a); System.out.println(Arrays.toString(a)); }
}
