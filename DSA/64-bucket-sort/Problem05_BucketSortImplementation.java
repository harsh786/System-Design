import java.util.*;
public class Problem05_BucketSortImplementation {
    public void bucketSort(float[] arr) {
        int n=arr.length;
        List<Float>[] buckets=new List[n];
        for(int i=0;i<n;i++) buckets[i]=new ArrayList<>();
        for(float x:arr) buckets[(int)(x*n)].add(x);
        for(List<Float> b:buckets) Collections.sort(b);
        int idx=0;
        for(List<Float> b:buckets) for(float x:b) arr[idx++]=x;
    }
    public static void main(String[] args){
        Problem05_BucketSortImplementation s=new Problem05_BucketSortImplementation();
        float[] arr={0.42f,0.32f,0.23f,0.52f,0.25f,0.47f,0.51f};
        s.bucketSort(arr);
        System.out.println(Arrays.toString(arr));
    }
}
