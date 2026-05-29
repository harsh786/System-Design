import java.util.*;
public class Problem19_RadixSortMSDvsLSD {
    public void lsdRadixSort(int[] arr) {
        int max=0; for(int x:arr) max=Math.max(max,x);
        for(int exp=1;max/exp>0;exp*=10){int[] out=new int[arr.length],c=new int[10];
            for(int x:arr) c[(x/exp)%10]++; for(int i=1;i<10;i++) c[i]+=c[i-1];
            for(int i=arr.length-1;i>=0;i--){out[c[(arr[i]/exp)%10]-1]=arr[i];c[(arr[i]/exp)%10]--;}
            System.arraycopy(out,0,arr,0,arr.length);}
    }
    public void msdRadixSort(int[] arr, int lo, int hi, int exp) {
        if(lo>=hi||exp<=0) return;
        int[] count=new int[12],out=new int[hi-lo+1];
        for(int i=lo;i<=hi;i++) count[(arr[i]/exp)%10+1]++;
        for(int i=1;i<11;i++) count[i]+=count[i-1];
        for(int i=lo;i<=hi;i++){out[count[(arr[i]/exp)%10]]=arr[i];count[(arr[i]/exp)%10]++;}
        System.arraycopy(out,0,arr,lo,hi-lo+1);
        // Recurse on each digit group
        if(exp>1) for(int i=lo;i<=hi;) {int d=(arr[i]/(exp))%10; int j=i; while(j<=hi&&(arr[j]/exp)%10==d) j++; msdRadixSort(arr,i,j-1,exp/10); i=j;}
    }
    public static void main(String[] args){
        Problem19_RadixSortMSDvsLSD s=new Problem19_RadixSortMSDvsLSD();
        int[] a1={170,45,75,90,802,24,2,66}; s.lsdRadixSort(a1); System.out.println("LSD: "+Arrays.toString(a1));
        int[] a2={170,45,75,90,802,24,2,66}; s.msdRadixSort(a2,0,a2.length-1,100); System.out.println("MSD: "+Arrays.toString(a2));
    }
}
