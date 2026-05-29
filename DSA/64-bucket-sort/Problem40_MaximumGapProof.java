import java.util.*;
public class Problem40_MaximumGapProof {
    /*
     * Pigeonhole proof: n numbers in range [min,max], n-1 gaps.
     * Average gap = (max-min)/(n-1). By pigeonhole, max gap >= average gap.
     * Bucket size = (max-min)/(n-1), so max gap is between buckets, not within.
     */
    public int maximumGap(int[] nums) {
        int n=nums.length; if(n<2) return 0;
        int min=Integer.MAX_VALUE,max=Integer.MIN_VALUE;
        for(int x:nums){min=Math.min(min,x);max=Math.max(max,x);}
        if(min==max) return 0;
        int gap=Math.max(1,(max-min)/(n-1));
        int buckets=(max-min)/gap+1;
        int[] bMin=new int[buckets],bMax=new int[buckets]; boolean[] used=new boolean[buckets];
        Arrays.fill(bMin,Integer.MAX_VALUE); Arrays.fill(bMax,Integer.MIN_VALUE);
        for(int x:nums){int i=(x-min)/gap;bMin[i]=Math.min(bMin[i],x);bMax[i]=Math.max(bMax[i],x);used[i]=true;}
        int maxGap=0,prev=bMax[0];
        for(int i=1;i<buckets;i++){if(!used[i]) continue;maxGap=Math.max(maxGap,bMin[i]-prev);prev=bMax[i];}
        return maxGap;
    }
    public static void main(String[] args){ System.out.println(new Problem40_MaximumGapProof().maximumGap(new int[]{3,6,9,1})); }
}
