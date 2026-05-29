/**
 * Problem 38: Find Good Days to Rob the Bank (LeetCode 2100)
 * 
 * Pattern: Prefix arrays tracking consecutive non-increasing from left and
 * consecutive non-decreasing from right. Day i is good if both >= time.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Finding stable periods in system metrics where values
 * have been declining for time days before and rising for time days after.
 */
import java.util.*;

public class Problem38_GoodDaysToRobBank {

    public static List<Integer> goodDaysToRobBank(int[] security, int time) {
        int n = security.length;
        int[] nonInc = new int[n]; // consecutive non-increasing days ending at i
        int[] nonDec = new int[n]; // consecutive non-decreasing days starting at i

        for (int i = 1; i < n; i++)
            if (security[i] <= security[i - 1]) nonInc[i] = nonInc[i - 1] + 1;
        for (int i = n - 2; i >= 0; i--)
            if (security[i] <= security[i + 1]) nonDec[i] = nonDec[i + 1] + 1;

        List<Integer> result = new ArrayList<>();
        for (int i = time; i < n - time; i++)
            if (nonInc[i] >= time && nonDec[i] >= time) result.add(i);
        return result;
    }

    public static void main(String[] args) {
        assert goodDaysToRobBank(new int[]{5,3,3,3,5,6,2}, 2).equals(Arrays.asList(2, 3));
        assert goodDaysToRobBank(new int[]{1,1,1,1,1}, 0).equals(Arrays.asList(0,1,2,3,4));
        assert goodDaysToRobBank(new int[]{1,2,3,4,5,6}, 2).equals(Collections.emptyList());
        System.out.println("All tests passed!");
    }
}
