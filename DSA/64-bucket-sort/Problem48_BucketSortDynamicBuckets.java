import java.util.*;
public class Problem48_BucketSortDynamicBuckets {
    /* Dynamically determine bucket count based on data distribution */
    public void sort(int[] arr) {
        int n=arr.length; if(n<=1) return;
        int min=Integer.MAX_VALUE,max=Integer.MIN_VALUE; for(int x:arr){min=Math.min(min,x);max=Math.max(max,x);}
        if(min==max) return;
        // Use Sturges' rule: k = ceil(log2(n)) + 1
        int numBuckets=(int)Math.ceil(Math.log(n)/Math.log(2))+1;
        int range=(max-min+numBuckets)/numBuckets;
        List<Integer>[] buckets=new List[numBuckets]; for(int i=0;i<numBuckets;i++) buckets[i]=new ArrayList<>();
        for(int x:arr) buckets[Math.min((x-min)/Math.max(range,1),numBuckets-1)].add(x);
        int idx=0; for(List<Integer> b:buckets){Collections.sort(b);for(int x:b) arr[idx++]=x;}
    }
    public static void main(String[] args){ int[] a={50,20,80,10,90,30,70,40,60,100,5,95}; new Problem48_BucketSortDynamicBuckets().sort(a); System.out.println(Arrays.toString(a)); }
}
