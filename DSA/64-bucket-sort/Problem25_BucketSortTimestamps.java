import java.util.*;
public class Problem25_BucketSortTimestamps {
    /* Sort timestamps into hourly buckets */
    public long[] sortTimestamps(long[] timestamps) {
        if(timestamps.length==0) return timestamps;
        long min=Long.MAX_VALUE,max=Long.MIN_VALUE;
        for(long t:timestamps){min=Math.min(min,t);max=Math.max(max,t);}
        int numBuckets=(int)((max-min)/3600)+1;
        List<Long>[] buckets=new List[numBuckets]; for(int i=0;i<numBuckets;i++) buckets[i]=new ArrayList<>();
        for(long t:timestamps) buckets[(int)((t-min)/3600)].add(t);
        int idx=0; for(List<Long> b:buckets){Collections.sort(b);for(long t:b) timestamps[idx++]=t;}
        return timestamps;
    }
    public static void main(String[] args){ Problem25_BucketSortTimestamps s=new Problem25_BucketSortTimestamps(); long[] ts={1000,500,7200,3700,100,7300}; s.sortTimestamps(ts); System.out.println(Arrays.toString(ts)); }
}
