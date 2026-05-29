import java.util.*;
public class Problem31_BucketVsComparisonSort {
    public void benchmark(int n) {
        Random r=new Random(42); double[] a=new double[n]; for(int i=0;i<n;i++) a[i]=r.nextDouble();
        double[] b=a.clone();
        long t1=System.nanoTime(); Arrays.sort(b); long t2=System.nanoTime();
        long t3=System.nanoTime(); bucketSort(a); long t4=System.nanoTime();
        System.out.printf("n=%d Comparison: %dms Bucket: %dms%n",n,(t2-t1)/1000000,(t4-t3)/1000000);
    }
    private void bucketSort(double[] a){int n=a.length;List<Double>[] b=new List[n];for(int i=0;i<n;i++) b[i]=new ArrayList<>();for(double x:a) b[(int)(x*n)>=n?n-1:(int)(x*n)].add(x);int idx=0;for(List<Double> bucket:b){Collections.sort(bucket);for(double x:bucket) a[idx++]=x;}}
    public static void main(String[] args){ new Problem31_BucketVsComparisonSort().benchmark(1000000); }
}
