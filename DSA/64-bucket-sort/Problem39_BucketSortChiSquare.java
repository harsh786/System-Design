import java.util.*;
public class Problem39_BucketSortChiSquare {
    public void sort(double[] arr) {
        int n=arr.length; double max=0; for(double x:arr) max=Math.max(max,x);
        int numBuckets=(int)Math.sqrt(n)+1;
        List<Double>[] buckets=new List[numBuckets]; for(int i=0;i<numBuckets;i++) buckets[i]=new ArrayList<>();
        for(double x:arr) buckets[Math.min((int)(x/max*numBuckets),numBuckets-1)].add(x);
        int idx=0; for(List<Double> b:buckets){Collections.sort(b);for(double x:b) arr[idx++]=x;}
    }
    public static void main(String[] args){ Random r=new Random(42); double[] a=new double[20]; for(int i=0;i<20;i++){double s=0;for(int j=0;j<3;j++){double g=r.nextGaussian();s+=g*g;}a[i]=s;} new Problem39_BucketSortChiSquare().sort(a); System.out.println(Arrays.toString(a)); }
}
