import java.util.*;

public class Problem12_RandomPickIndex {
    // 398. Random Pick Index: Given array with duplicates, randomly pick index of target.
    
    int[] nums;
    Random rand = new Random();
    
    public Problem12_RandomPickIndex() { this.nums = new int[0]; }
    
    public void init(int[] nums) { this.nums = nums; }
    
    public int pick(int target) {
        int count = 0, result = -1;
        for (int i = 0; i < nums.length; i++) {
            if (nums[i] == target) {
                count++;
                if (rand.nextInt(count) == 0) result = i;
            }
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem12_RandomPickIndex sol = new Problem12_RandomPickIndex();
        sol.init(new int[]{1,2,3,3,3});
        System.out.println("Pick 3: index=" + sol.pick(3));
        System.out.println("Pick 1: index=" + sol.pick(1));
    }
}
