import java.util.*;
public class Problem41_FrequencySortBuckets {
    public int[] frequencySort(int[] nums) {
        Map<Integer,Integer> freq=new HashMap<>(); for(int n:nums) freq.merge(n,1,Integer::sum);
        List<Integer>[] buckets=new List[nums.length+1]; for(int i=0;i<buckets.length;i++) buckets[i]=new ArrayList<>();
        for(Map.Entry<Integer,Integer> e:freq.entrySet()) buckets[e.getValue()].add(e.getKey());
        int[] res=new int[nums.length]; int idx=0;
        for(int i=1;i<buckets.length;i++) for(int v:buckets[i]) for(int j=0;j<i;j++) res[idx++]=v;
        return res;
    }
    public static void main(String[] args){ System.out.println(Arrays.toString(new Problem41_FrequencySortBuckets().frequencySort(new int[]{1,1,2,2,2,3}))); }
}
