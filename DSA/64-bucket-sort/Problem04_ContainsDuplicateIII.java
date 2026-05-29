import java.util.*;
public class Problem04_ContainsDuplicateIII {
    public boolean containsNearbyAlmostDuplicate(int[] nums, int indexDiff, int valueDiff) {
        if(valueDiff<0) return false;
        Map<Long,Long> buckets=new HashMap<>();
        long w=(long)valueDiff+1;
        for(int i=0;i<nums.length;i++){
            long id=getID(nums[i],w);
            if(buckets.containsKey(id)) return true;
            if(buckets.containsKey(id-1)&&Math.abs(nums[i]-buckets.get(id-1))<=valueDiff) return true;
            if(buckets.containsKey(id+1)&&Math.abs(nums[i]-buckets.get(id+1))<=valueDiff) return true;
            buckets.put(id,(long)nums[i]);
            if(i>=indexDiff) buckets.remove(getID(nums[i-indexDiff],w));
        }
        return false;
    }
    private long getID(long x,long w){return x<0?(x+1)/w-1:x/w;}
    public static void main(String[] args){
        Problem04_ContainsDuplicateIII s=new Problem04_ContainsDuplicateIII();
        System.out.println(s.containsNearbyAlmostDuplicate(new int[]{1,2,3,1},3,0)); // true
    }
}
