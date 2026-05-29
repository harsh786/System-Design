import java.util.*;

public class Problem29_ClosestSubsequenceSum {
    public int minAbsDifference(int[] nums, int goal) {
        int n = nums.length, half = n/2;
        int[] left = Arrays.copyOfRange(nums,0,half), right = Arrays.copyOfRange(nums,half,n);
        List<Integer> lSums = allSums(left), rSums = allSums(right);
        Collections.sort(rSums);
        int ans = Integer.MAX_VALUE;
        for (int ls : lSums) {
            int target = goal - ls;
            int idx = Collections.binarySearch(rSums, target);
            if (idx >= 0) return 0;
            idx = -idx - 1;
            if (idx < rSums.size()) ans = Math.min(ans, Math.abs(target - rSums.get(idx)));
            if (idx > 0) ans = Math.min(ans, Math.abs(target - rSums.get(idx-1)));
        }
        return ans;
    }
    private List<Integer> allSums(int[] arr) {
        List<Integer> sums = new ArrayList<>();
        for (int mask = 0; mask < (1<<arr.length); mask++) { int s=0; for (int i=0;i<arr.length;i++) if ((mask&(1<<i))!=0) s+=arr[i]; sums.add(s); }
        return sums;
    }
    public static void main(String[] args) { System.out.println(new Problem29_ClosestSubsequenceSum().minAbsDifference(new int[]{5,-7,3,5},6)); }
}
