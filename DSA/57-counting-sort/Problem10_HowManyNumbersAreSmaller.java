import java.util.*;

public class Problem10_HowManyNumbersAreSmaller {
    public static int[] smallerNumbersThanCurrent(int[] nums) {
        int[] count = new int[101];
        for (int n : nums) count[n]++;
        // prefix sum
        for (int i = 1; i <= 100; i++) count[i] += count[i-1];
        int[] result = new int[nums.length];
        for (int i = 0; i < nums.length; i++) result[i] = nums[i] == 0 ? 0 : count[nums[i]-1];
        return result;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(smallerNumbersThanCurrent(new int[]{8,1,2,2,3})));
        // [4,0,1,1,3]
    }
}
