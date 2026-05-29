import java.util.*;

public class Problem29_MajorityElement {
    /* Boyer-Moore Voting */
    public int majorityElement(int[] nums) {
        int candidate = 0, count = 0;
        for (int n : nums) {
            if (count == 0) candidate = n;
            count += (n == candidate) ? 1 : -1;
        }
        return candidate;
    }

    public static void main(String[] args) {
        Problem29_MajorityElement sol = new Problem29_MajorityElement();
        System.out.println(sol.majorityElement(new int[]{2, 2, 1, 1, 1, 2, 2})); // 2
    }
}
