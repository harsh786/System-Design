import java.util.Arrays;

public class Problem46_NextPermutation {
    public void nextPermutation(int[] nums) {
        int n = nums.length, i = n-2;
        while (i >= 0 && nums[i] >= nums[i+1]) i--;
        if (i >= 0) { int j = n-1; while (nums[j] <= nums[i]) j--; int t=nums[i];nums[i]=nums[j];nums[j]=t; }
        // reverse i+1 to end
        int lo=i+1,hi=n-1; while(lo<hi){int t=nums[lo];nums[lo]=nums[hi];nums[hi]=t;lo++;hi--;}
    }
    public static void main(String[] args) { int[] a={1,2,3}; new Problem46_NextPermutation().nextPermutation(a); System.out.println(Arrays.toString(a)); }
}
