import java.util.*;
public class Problem02_TopKFrequentBucket {
    public int[] topKFrequent(int[] nums, int k) {
        Map<Integer,Integer> freq=new HashMap<>();
        for(int n:nums) freq.merge(n,1,Integer::sum);
        List<Integer>[] buckets=new List[nums.length+1];
        for(int i=0;i<buckets.length;i++) buckets[i]=new ArrayList<>();
        for(Map.Entry<Integer,Integer> e:freq.entrySet()) buckets[e.getValue()].add(e.getKey());
        int[] res=new int[k]; int idx=0;
        for(int i=buckets.length-1;i>=0&&idx<k;i--) for(int v:buckets[i]) {res[idx++]=v;if(idx==k) break;}
        return res;
    }
    public static void main(String[] args){
        Problem02_TopKFrequentBucket s=new Problem02_TopKFrequentBucket();
        System.out.println(Arrays.toString(s.topKFrequent(new int[]{1,1,1,2,2,3},2)));
    }
}
