import java.util.*;
public class Problem33_BucketSortWithInsertionSort {
    public void sort(double[] arr) {
        int n=arr.length,numBuckets=(int)Math.sqrt(n)+1;
        List<Double>[] buckets=new List[numBuckets]; for(int i=0;i<numBuckets;i++) buckets[i]=new ArrayList<>();
        for(double x:arr) buckets[Math.min((int)(x*numBuckets),numBuckets-1)].add(x);
        int idx=0; for(List<Double> b:buckets){insertionSort(b);for(double x:b) arr[idx++]=x;}
    }
    private void insertionSort(List<Double> list){for(int i=1;i<list.size();i++){double key=list.get(i);int j=i-1;while(j>=0&&list.get(j)>key){list.set(j+1,list.get(j));j--;}list.set(j+1,key);}}
    public static void main(String[] args){ double[] a={0.78,0.17,0.39,0.26,0.72,0.94,0.21,0.12,0.23,0.68}; new Problem33_BucketSortWithInsertionSort().sort(a); System.out.println(Arrays.toString(a)); }
}
