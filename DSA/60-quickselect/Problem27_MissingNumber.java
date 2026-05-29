import java.util.*;

public class Problem27_MissingNumber {
    public int missingNumber(int[] nums) {
        int n = nums.length, xor = n;
        for (int i = 0; i < n; i++) xor ^= i ^ nums[i];
        return xor;
    }

    public static void main(String[] args) {
        Problem27_MissingNumber sol = new Problem27_MissingNumber();
        System.out.println(sol.missingNumber(new int[]{3, 0, 1})); // 2
    }
}
