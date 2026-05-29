import java.util.*;
public class Problem17_RadixSortIntegers {
    public void radixSort(int[] arr) {
        int max=0; for(int x:arr) max=Math.max(max,Math.abs(x));
        // Handle negatives: offset
        int offset=-Integer.MAX_VALUE; for(int x:arr) offset=Math.min(offset,x); offset=-offset;
        for(int i=0;i<arr.length;i++) arr[i]+=offset;
        max=0; for(int x:arr) max=Math.max(max,x);
        for(int exp=1;max/exp>0;exp*=10){
            int[] output=new int[arr.length],count=new int[10];
            for(int x:arr) count[(x/exp)%10]++;
            for(int i=1;i<10;i++) count[i]+=count[i-1];
            for(int i=arr.length-1;i>=0;i--){output[count[(arr[i]/exp)%10]-1]=arr[i];count[(arr[i]/exp)%10]--;}
            System.arraycopy(output,0,arr,0,arr.length);
        }
        for(int i=0;i<arr.length;i++) arr[i]-=offset;
    }
    public static void main(String[] args){ Problem17_RadixSortIntegers s=new Problem17_RadixSortIntegers(); int[] a={170,-45,75,-90,802,24,2,66}; s.radixSort(a); System.out.println(Arrays.toString(a)); }
}
