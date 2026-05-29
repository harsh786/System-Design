import java.util.*;
public class Problem50_BucketSortPerformanceAnalysis {
    public void analyze() {
        int[] sizes={1000,10000,100000,1000000};
        for(int n:sizes){
            Random r=new Random(42); double[] uniform=new double[n]; for(int i=0;i<n;i++) uniform[i]=r.nextDouble();
            double[] skewed=new double[n]; for(int i=0;i<n;i++) skewed[i]=Math.pow(r.nextDouble(),3);
            long t1=System.nanoTime(); bucketSort(uniform.clone()); long t2=System.nanoTime();
            long t3=System.nanoTime(); bucketSort(skewed.clone()); long t4=System.nanoTime();
            long t5=System.nanoTime(); Arrays.sort(uniform.clone()); long t6=System.nanoTime();
            System.out.printf("n=%7d | Bucket(uniform):%4dms Bucket(skewed):%4dms Arrays.sort:%4dms%n",n,(t2-t1)/1000000,(t4-t3)/1000000,(t6-t5)/1000000);
        }
    }
    private void bucketSort(double[] a){int n=a.length;List<Double>[] b=new List[n];for(int i=0;i<n;i++) b[i]=new ArrayList<>();for(double x:a) b[Math.min((int)(x*n),n-1)].add(x);int idx=0;for(List<Double> bucket:b){Collections.sort(bucket);for(double x:bucket) a[idx++]=x;}}
    public static void main(String[] args){ new Problem50_BucketSortPerformanceAnalysis().analyze(); }
}
