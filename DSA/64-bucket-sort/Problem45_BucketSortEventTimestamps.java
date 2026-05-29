import java.util.*;
public class Problem45_BucketSortEventTimestamps {
    /* Sort events by timestamp into minute-level buckets */
    public long[] sort(long[] timestamps) {
        if(timestamps.length==0) return timestamps;
        long min=Long.MAX_VALUE,max=Long.MIN_VALUE; for(long t:timestamps){min=Math.min(min,t);max=Math.max(max,t);}
        int numBuckets=(int)((max-min)/60)+1;
        List<Long>[] buckets=new List[numBuckets]; for(int i=0;i<numBuckets;i++) buckets[i]=new ArrayList<>();
        for(long t:timestamps) buckets[(int)((t-min)/60)].add(t);
        int idx=0; for(List<Long> b:buckets){Collections.sort(b);for(long t:b) timestamps[idx++]=t;}
        return timestamps;
    }
    public static void main(String[] args){ long[] ts={300,60,180,120,240,30,90}; new Problem45_BucketSortEventTimestamps().sort(ts); System.out.println(Arrays.toString(ts)); }
}
