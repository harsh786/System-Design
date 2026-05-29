import java.util.*;
public class Problem49_AdaptiveBucketSort {
    /* If variance is high, use more buckets; if low, fewer */
    public void sort(double[] arr) {
        int n=arr.length; if(n<=1) return;
        double mean=0; for(double x:arr) mean+=x; mean/=n;
        double var=0; for(double x:arr) var+=(x-mean)*(x-mean); var/=n;
        double min=Double.MAX_VALUE,max=-Double.MAX_VALUE; for(double x:arr){min=Math.min(min,x);max=Math.max(max,x);}
        // High variance -> more buckets
        int numBuckets=Math.max(2,Math.min(n,(int)(Math.sqrt(n)*Math.sqrt(var)/((max-min)/n+0.001))));
        numBuckets=Math.min(numBuckets,n);
        double width=(max-min)/numBuckets+0.001;
        List<Double>[] buckets=new List[numBuckets]; for(int i=0;i<numBuckets;i++) buckets[i]=new ArrayList<>();
        for(double x:arr) buckets[Math.min((int)((x-min)/width),numBuckets-1)].add(x);
        int idx=0; for(List<Double> b:buckets){Collections.sort(b);for(double x:b) arr[idx++]=x;}
    }
    public static void main(String[] args){ Random r=new Random(42); double[] a=new double[20]; for(int i=0;i<20;i++) a[i]=r.nextGaussian()*10+50; new Problem49_AdaptiveBucketSort().sort(a); System.out.println(Arrays.toString(a)); }
}
