import java.util.*;
public class Problem12_SortFloatingPoint {
    public void sort(double[] arr) {
        int n=arr.length; List<Double>[] buckets=new List[n];
        for(int i=0;i<n;i++) buckets[i]=new ArrayList<>();
        double min=Double.MAX_VALUE,max=Double.MIN_VALUE;
        for(double x:arr){min=Math.min(min,x);max=Math.max(max,x);}
        double range=max-min+0.001;
        for(double x:arr) buckets[(int)((x-min)/range*n) >= n ? n-1 : (int)((x-min)/range*n)].add(x);
        int idx=0; for(List<Double> b:buckets){Collections.sort(b);for(double x:b) arr[idx++]=x;}
    }
    public static void main(String[] args){ Problem12_SortFloatingPoint s=new Problem12_SortFloatingPoint(); double[] a={0.42,0.32,0.23,0.52,0.25}; s.sort(a); System.out.println(Arrays.toString(a)); }
}
