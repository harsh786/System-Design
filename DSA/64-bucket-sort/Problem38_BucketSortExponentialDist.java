import java.util.*;
public class Problem38_BucketSortExponentialDist {
    /* For exponential distribution, use log-spaced buckets */
    public void sort(double[] arr, double lambda) {
        int n=arr.length,numBuckets=(int)Math.sqrt(n)+1;
        double maxVal=0; for(double x:arr) maxVal=Math.max(maxVal,x);
        List<Double>[] buckets=new List[numBuckets]; for(int i=0;i<numBuckets;i++) buckets[i]=new ArrayList<>();
        for(double x:arr){int idx=(int)(numBuckets*(1-Math.exp(-lambda*x))); buckets[Math.min(idx,numBuckets-1)].add(x);}
        int idx=0; for(List<Double> b:buckets){Collections.sort(b);for(double x:b) arr[idx++]=x;}
    }
    public static void main(String[] args){ Random r=new Random(42); double[] a=new double[20]; for(int i=0;i<20;i++) a[i]=-Math.log(1-r.nextDouble())/0.5; new Problem38_BucketSortExponentialDist().sort(a,0.5); System.out.println(Arrays.toString(a)); }
}
