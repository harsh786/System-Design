/**
 * Problem 43: Third Maximum Number
 * Return third distinct maximum. If not exists, return the maximum.
 * 
 * Production Analogy: Like finding the 3rd highest priority alert level 
 * for escalation routing.
 * 
 * O(n) time, O(1) space - track top 3 using Long.MIN_VALUE sentinels
 */
public class Problem43_ThirdMaximumNumber {

    public static int thirdMax(int[] nums) {
        long first = Long.MIN_VALUE, second = Long.MIN_VALUE, third = Long.MIN_VALUE;
        for (int n : nums) {
            if (n == first || n == second || n == third) continue;
            if (n > first) { third = second; second = first; first = n; }
            else if (n > second) { third = second; second = n; }
            else if (n > third) { third = n; }
        }
        return third == Long.MIN_VALUE ? (int) first : (int) third;
    }

    public static void main(String[] args) {
        System.out.println(thirdMax(new int[]{3,2,1}));   // 1
        System.out.println(thirdMax(new int[]{1,2}));     // 2
        System.out.println(thirdMax(new int[]{2,2,3,1})); // 1
    }
}
