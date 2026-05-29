import java.util.*;
public class Problem08_DistributionSort {
    /* Distribution/Counting sort for known range */
    public void distributionSort(int[] arr, int maxVal) {
        int[] count=new int[maxVal+1];
        for(int x:arr) count[x]++;
        int idx=0;
        for(int i=0;i<=maxVal;i++) while(count[i]-->0) arr[idx++]=i;
    }
    public static void main(String[] args){
        Problem08_DistributionSort s=new Problem08_DistributionSort();
        int[] arr={4,2,2,8,3,3,1};
        s.distributionSort(arr,8);
        System.out.println(Arrays.toString(arr));
    }
}
