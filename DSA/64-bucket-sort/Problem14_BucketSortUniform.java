import java.util.*;
public class Problem14_BucketSortUniform {
    /* Optimal O(n) when data is uniformly distributed */
    public void sort(double[] arr) {
        int n=arr.length; List<Double>[] b=new List[n]; for(int i=0;i<n;i++) b[i]=new ArrayList<>();
        for(double x:arr) b[Math.min((int)(x*n),n-1)].add(x);
        int idx=0; for(List<Double> bucket:b){Collections.sort(bucket);for(double x:bucket) arr[idx++]=x;}
    }
    public static void main(String[] args){ Problem14_BucketSortUniform s=new Problem14_BucketSortUniform(); double[] a=new double[20]; Random r=new Random(42); for(int i=0;i<20;i++) a[i]=r.nextDouble(); s.sort(a); System.out.println(Arrays.toString(a)); }
}
