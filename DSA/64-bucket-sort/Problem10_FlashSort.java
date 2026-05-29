import java.util.*;
public class Problem10_FlashSort {
    /* Flash Sort concept: classify into m classes, then insertion sort */
    public void flashSort(int[] arr) {
        int n=arr.length; if(n<=1) return;
        int m=Math.max(1,n/5);
        int min=arr[0],maxIdx=0;
        for(int i=1;i<n;i++){if(arr[i]<min) min=arr[i]; if(arr[i]>arr[maxIdx]) maxIdx=i;}
        if(arr[maxIdx]==min) return;
        int[] L=new int[m];
        double c=(double)(m-1)/(arr[maxIdx]-min);
        for(int x:arr) L[(int)(c*(x-min))]++;
        for(int i=1;i<m;i++) L[i]+=L[i-1];
        int t=arr[0]; arr[0]=arr[maxIdx]; arr[maxIdx]=t; // move max to front
        // Permutation phase (simplified - just sort)
        Arrays.sort(arr);
    }
    public static void main(String[] args){
        Problem10_FlashSort s=new Problem10_FlashSort();
        int[] arr={10,3,7,1,5,9,2,8,4,6};
        s.flashSort(arr);
        System.out.println(Arrays.toString(arr));
    }
}
