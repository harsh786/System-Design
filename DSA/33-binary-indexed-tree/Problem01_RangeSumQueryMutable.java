import java.util.*;

public class Problem01_RangeSumQueryMutable {
    int[] bit;
    int[] nums;
    int n;

    public Problem01_RangeSumQueryMutable(int[] nums) {
        this.n = nums.length;
        this.nums = new int[n];
        this.bit = new int[n + 1];
        for (int i = 0; i < n; i++) update(i, nums[i]);
        this.nums = nums.clone();
    }

    void update(int i, int val) {
        int diff = val - nums[i];
        nums[i] = val;
        for (int idx = i + 1; idx <= n; idx += idx & (-idx))
            bit[idx] += diff;
    }

    int prefixSum(int i) {
        int sum = 0;
        for (int idx = i + 1; idx > 0; idx -= idx & (-idx))
            sum += bit[idx];
        return sum;
    }

    int sumRange(int l, int r) {
        return prefixSum(r) - (l > 0 ? prefixSum(l - 1) : 0);
    }

    public static void main(String[] args) {
        int[] nums = {1, 3, 5};
        Problem01_RangeSumQueryMutable obj = new Problem01_RangeSumQueryMutable(nums);
        System.out.println(obj.sumRange(0, 2)); // 9
        obj.update(1, 2);
        System.out.println(obj.sumRange(0, 2)); // 8
    }
}
