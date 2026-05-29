import java.util.*;
public class Problem42_KMostFrequentBuckets {
    public List<Integer> kMostFrequent(int[] nums, int k) {
        Map<Integer,Integer> freq=new HashMap<>(); for(int n:nums) freq.merge(n,1,Integer::sum);
        List<Integer>[] buckets=new List[nums.length+1]; for(int i=0;i<buckets.length;i++) buckets[i]=new ArrayList<>();
        for(Map.Entry<Integer,Integer> e:freq.entrySet()) buckets[e.getValue()].add(e.getKey());
        List<Integer> res=new ArrayList<>();
        for(int i=buckets.length-1;i>=0&&res.size()<k;i--) for(int v:buckets[i]){res.add(v);if(res.size()==k) break;}
        return res;
    }
    public static void main(String[] args){ System.out.println(new Problem42_KMostFrequentBuckets().kMostFrequent(new int[]{1,1,1,2,2,3},2)); }
}
