import java.util.*;
public class Problem01_MaximumGap {
    public int maximumGap(int[] nums) {
        int n=nums.length; if(n<2) return 0;
        int min=Integer.MAX_VALUE,max=Integer.MIN_VALUE;
        for(int x:nums){min=Math.min(min,x);max=Math.max(max,x);}
        if(min==max) return 0;
        int bucketSize=Math.max(1,(max-min)/(n-1));
        int bucketCount=(max-min)/bucketSize+1;
        int[] bucketMin=new int[bucketCount],bucketMax=new int[bucketCount];
        Arrays.fill(bucketMin,Integer.MAX_VALUE); Arrays.fill(bucketMax,Integer.MIN_VALUE);
        for(int x:nums){int idx=(x-min)/bucketSize;bucketMin[idx]=Math.min(bucketMin[idx],x);bucketMax[idx]=Math.max(bucketMax[idx],x);}
        int maxGap=0,prev=bucketMax[0];
        for(int i=1;i<bucketCount;i++){if(bucketMin[i]==Integer.MAX_VALUE) continue;maxGap=Math.max(maxGap,bucketMin[i]-prev);prev=bucketMax[i];}
        return maxGap;
    }
    public static void main(String[] args){
        Problem01_MaximumGap s=new Problem01_MaximumGap();
        System.out.println(s.maximumGap(new int[]{3,6,9,1})); // 3
    }
}
