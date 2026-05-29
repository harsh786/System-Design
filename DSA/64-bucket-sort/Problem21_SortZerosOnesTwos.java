import java.util.*;
public class Problem21_SortZerosOnesTwos {
    public void sort(int[] arr) { int lo=0,mid=0,hi=arr.length-1; while(mid<=hi){if(arr[mid]==0){int t=arr[lo];arr[lo]=arr[mid];arr[mid]=t;lo++;mid++;}else if(arr[mid]==2){int t=arr[mid];arr[mid]=arr[hi];arr[hi]=t;hi--;}else mid++;} }
    public static void main(String[] args){ int[] a={0,1,2,1,0,2,1,0}; new Problem21_SortZerosOnesTwos().sort(a); System.out.println(Arrays.toString(a)); }
}
