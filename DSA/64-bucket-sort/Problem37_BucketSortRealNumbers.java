import java.util.*;
public class Problem37_BucketSortRealNumbers {
    /* Sort real numbers in [0,1) */
    public void sort(double[] arr) {
        int n=arr.length; List<Double>[] b=new List[n]; for(int i=0;i<n;i++) b[i]=new ArrayList<>();
        for(double x:arr) b[(int)(x*n)].add(x);
        int idx=0; for(List<Double> bucket:b){Collections.sort(bucket);for(double x:bucket) arr[idx++]=x;}
    }
    public static void main(String[] args){ double[] a={0.897,0.565,0.656,0.1234,0.665,0.3434}; new Problem37_BucketSortRealNumbers().sort(a); System.out.println(Arrays.toString(a)); }
}
