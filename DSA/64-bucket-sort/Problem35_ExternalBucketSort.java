import java.util.*;
public class Problem35_ExternalBucketSort {
    /* Simulate external bucket sort where each bucket is a "file" */
    public int[] sort(int[] data, int maxMemory) {
        int min=Integer.MAX_VALUE,max=Integer.MIN_VALUE; for(int x:data){min=Math.min(min,x);max=Math.max(max,x);}
        int numBuckets=(data.length+maxMemory-1)/maxMemory;
        List<Integer>[] files=new List[numBuckets]; for(int i=0;i<numBuckets;i++) files[i]=new ArrayList<>();
        int range=(max-min+numBuckets)/numBuckets;
        for(int x:data) files[Math.min((x-min)/Math.max(range,1),numBuckets-1)].add(x);
        int idx=0; for(List<Integer> f:files){Collections.sort(f);for(int x:f) data[idx++]=x;}
        return data;
    }
    public static void main(String[] args){ int[] a={90,20,50,10,80,30,70,40,60}; new Problem35_ExternalBucketSort().sort(a,3); System.out.println(Arrays.toString(a)); }
}
