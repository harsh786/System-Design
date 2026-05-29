import java.util.*;

public class Problem21_SortArrayByParityII {
    public int[] sortArrayByParityII(int[] nums) {
        int even = 0, odd = 1, n = nums.length;
        while (even < n && odd < n) {
            while (even < n && nums[even] % 2 == 0) even += 2;
            while (odd < n && nums[odd] % 2 == 1) odd += 2;
            if (even < n && odd < n) { int t = nums[even]; nums[even] = nums[odd]; nums[odd] = t; }
        }
        return nums;
    }

    public static void main(String[] args) {
        Problem21_SortArrayByParityII sol = new Problem21_SortArrayByParityII();
        System.out.println(Arrays.toString(sol.sortArrayByParityII(new int[]{4,2,5,7})));
    }
}
