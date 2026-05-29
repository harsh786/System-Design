/**
 * Problem: Majority Element II (LeetCode 229)
 * Approach: Boyer-Moore extended - at most 2 candidates for >n/3
 * Complexity: O(n) time, O(1) space
 * Production Analogy: Detecting dominant patterns in network traffic analysis
 */
import java.util.*;
public class Problem08_MajorityElementII {
    public List<Integer> majorityElement(int[] nums) {
        int c1=0,c2=0,cnt1=0,cnt2=0;
        for (int n : nums) {
            if (n==c1) cnt1++;
            else if (n==c2) cnt2++;
            else if (cnt1==0) { c1=n; cnt1=1; }
            else if (cnt2==0) { c2=n; cnt2=1; }
            else { cnt1--; cnt2--; }
        }
        cnt1=0; cnt2=0;
        for (int n : nums) { if (n==c1) cnt1++; else if (n==c2) cnt2++; }
        List<Integer> res = new ArrayList<>();
        if (cnt1 > nums.length/3) res.add(c1);
        if (cnt2 > nums.length/3) res.add(c2);
        return res;
    }
    public static void main(String[] args) {
        System.out.println(new Problem08_MajorityElementII().majorityElement(new int[]{3,2,3})); // [3]
    }
}
