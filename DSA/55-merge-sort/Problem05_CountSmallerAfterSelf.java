import java.util.*;

public class Problem05_CountSmallerAfterSelf {
    static int[] count;
    
    static List<Integer> countSmaller(int[] nums) {
        int n=nums.length; count=new int[n];
        int[][] indexed=new int[n][2];
        for(int i=0;i<n;i++)indexed[i]=new int[]{nums[i],i};
        mergeSort(indexed,0,n-1);
        List<Integer> res=new ArrayList<>();
        for(int c2:count)res.add(c2);return res;
    }
    
    static void mergeSort(int[][] arr,int lo,int hi){
        if(lo>=hi)return;int mid=(lo+hi)/2;
        mergeSort(arr,lo,mid);mergeSort(arr,mid+1,hi);
        merge(arr,lo,mid,hi);
    }
    
    static void merge(int[][] arr,int lo,int mid,int hi){
        int[][] tmp=new int[hi-lo+1][2];int i=lo,j=mid+1,k=0;
        while(i<=mid&&j<=hi){
            if(arr[i][0]<=arr[j][0]){count[arr[i][1]]+=j-(mid+1);tmp[k++]=arr[i++];}
            else tmp[k++]=arr[j++];
        }
        while(i<=mid){count[arr[i][1]]+=j-(mid+1);tmp[k++]=arr[i++];}
        while(j<=hi)tmp[k++]=arr[j++];
        System.arraycopy(tmp,0,arr,lo,tmp.length);
    }
    
    public static void main(String[] args) {
        System.out.println(countSmaller(new int[]{5,2,6,1})); // [2,1,1,0]
    }
}
