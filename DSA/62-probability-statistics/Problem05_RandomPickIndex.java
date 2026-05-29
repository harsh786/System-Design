import java.util.*;

public class Problem05_RandomPickIndex {
    private int[] nums;
    private Random rand = new Random();

    public Problem05_RandomPickIndex(int[] nums) { this.nums = nums; }

    public int pick(int target) {
        int result = -1, count = 0;
        for (int i = 0; i < nums.length; i++) {
            if (nums[i] == target) { count++; if (rand.nextInt(count) == 0) result = i; }
        }
        return result;
    }

    public static void main(String[] args) {
        Problem05_RandomPickIndex sol = new Problem05_RandomPickIndex(new int[]{1,2,3,3,3});
        int[] freq = new int[5];
        for (int i = 0; i < 9000; i++) freq[sol.pick(3)]++;
        System.out.println(Arrays.toString(freq));
    }
}
