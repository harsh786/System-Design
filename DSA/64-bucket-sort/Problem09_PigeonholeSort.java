import java.util.*;
public class Problem09_PigeonholeSort {
    public void pigeonholeSort(int[] arr) {
        int min=Integer.MAX_VALUE,max=Integer.MIN_VALUE;
        for(int x:arr){min=Math.min(min,x);max=Math.max(max,x);}
        int range=max-min+1;
        int[] holes=new int[range];
        for(int x:arr) holes[x-min]++;
        int idx=0;
        for(int i=0;i<range;i++) while(holes[i]-->0) arr[idx++]=i+min;
    }
    public static void main(String[] args){
        Problem09_PigeonholeSort s=new Problem09_PigeonholeSort();
        int[] arr={8,3,2,7,4,6,8};
        s.pigeonholeSort(arr);
        System.out.println(Arrays.toString(arr));
    }
}
