import java.util.*;

public class Problem32_ContainsDuplicate {
    public boolean containsDuplicate(int[] nums) {
        Set<Integer> set = new HashSet<>();
        for (int n : nums) if (!set.add(n)) return true;
        return false;
    }

    public static void main(String[] args) {
        Problem32_ContainsDuplicate sol = new Problem32_ContainsDuplicate();
        System.out.println(sol.containsDuplicate(new int[]{1,2,3,1})); // true
        System.out.println(sol.containsDuplicate(new int[]{1,2,3,4})); // false
    }
}
