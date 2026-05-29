import java.util.*;

public class Problem25_FindDuplicateNumber {
    /* Floyd's cycle detection */
    public int findDuplicate(int[] nums) {
        int slow = nums[0], fast = nums[0];
        do { slow = nums[slow]; fast = nums[nums[fast]]; } while (slow != fast);
        slow = nums[0];
        while (slow != fast) { slow = nums[slow]; fast = nums[fast]; }
        return slow;
    }

    public static void main(String[] args) {
        Problem25_FindDuplicateNumber sol = new Problem25_FindDuplicateNumber();
        System.out.println(sol.findDuplicate(new int[]{1,3,4,2,2})); // 2
    }
}
