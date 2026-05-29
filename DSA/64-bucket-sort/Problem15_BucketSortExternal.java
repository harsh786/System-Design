import java.util.*;
public class Problem15_BucketSortExternal {
    /* Concept: partition data into buckets that fit in memory, sort each */
    public int[] externalSort(int[] data, int memoryLimit) {
        int min=Integer.MAX_VALUE,max=Integer.MIN_VALUE;
        for(int x:data){min=Math.min(min,x);max=Math.max(max,x);}
        int numBuckets=(data.length+memoryLimit-1)/memoryLimit;
        int range=(max-min+1+numBuckets-1)/numBuckets;
        List<Integer>[] buckets=new List[numBuckets]; for(int i=0;i<numBuckets;i++) buckets[i]=new ArrayList<>();
        for(int x:data) buckets[Math.min((x-min)/range,numBuckets-1)].add(x);
        int idx=0; for(List<Integer> b:buckets){Collections.sort(b);for(int x:b) data[idx++]=x;}
        return data;
    }
    public static void main(String[] args){ Problem15_BucketSortExternal s=new Problem15_BucketSortExternal(); int[] a={50,20,80,10,90,30,70,40,60}; s.externalSort(a,3); System.out.println(Arrays.toString(a)); }
}
