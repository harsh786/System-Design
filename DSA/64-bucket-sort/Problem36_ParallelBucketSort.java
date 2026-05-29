import java.util.*;
public class Problem36_ParallelBucketSort {
    /* Concept: each bucket sorted independently - embarrassingly parallel */
    public void sort(double[] arr) {
        int n=arr.length,numBuckets=Runtime.getRuntime().availableProcessors();
        List<Double>[] buckets=new List[numBuckets]; for(int i=0;i<numBuckets;i++) buckets[i]=new ArrayList<>();
        for(double x:arr) buckets[Math.min((int)(x*numBuckets),numBuckets-1)].add(x);
        // In practice each bucket.sort() runs on separate thread
        for(List<Double> b:buckets) Collections.sort(b);
        int idx=0; for(List<Double> b:buckets) for(double x:b) arr[idx++]=x;
    }
    public static void main(String[] args){ Random r=new Random(42); double[] a=new double[20]; for(int i=0;i<20;i++) a[i]=r.nextDouble(); new Problem36_ParallelBucketSort().sort(a); System.out.println(Arrays.toString(a)); }
}
