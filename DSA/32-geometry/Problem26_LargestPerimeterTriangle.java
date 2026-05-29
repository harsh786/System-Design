import java.util.*;

public class Problem26_LargestPerimeterTriangle {
    public static int largestPerimeter(int[] nums) {
        Arrays.sort(nums);
        for (int i = nums.length - 1; i >= 2; i--)
            if (nums[i-1] + nums[i-2] > nums[i]) return nums[i] + nums[i-1] + nums[i-2];
        return 0;
    }
    public static void main(String[] args) {
        System.out.println(largestPerimeter(new int[]{2,1,2})); // 5
    }
}
