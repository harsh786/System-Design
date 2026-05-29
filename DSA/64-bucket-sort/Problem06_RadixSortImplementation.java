import java.util.*;
public class Problem06_RadixSortImplementation {
    public void radixSort(int[] arr) {
        int max=0; for(int x:arr) max=Math.max(max,x);
        for(int exp=1;max/exp>0;exp*=10) countSort(arr,exp);
    }
    private void countSort(int[] arr,int exp){
        int n=arr.length; int[] output=new int[n],count=new int[10];
        for(int x:arr) count[(x/exp)%10]++;
        for(int i=1;i<10;i++) count[i]+=count[i-1];
        for(int i=n-1;i>=0;i--){output[count[(arr[i]/exp)%10]-1]=arr[i];count[(arr[i]/exp)%10]--;}
        System.arraycopy(output,0,arr,0,n);
    }
    public static void main(String[] args){
        Problem06_RadixSortImplementation s=new Problem06_RadixSortImplementation();
        int[] arr={170,45,75,90,802,24,2,66};
        s.radixSort(arr);
        System.out.println(Arrays.toString(arr));
    }
}
