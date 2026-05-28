/**
 * Problem 10: Assign Cookies (LeetCode 455)
 *
 * Greedy Choice: Sort both arrays. Assign smallest sufficient cookie to least greedy child.
 *
 * Time: O(n log n), Space: O(1)
 *
 * Production Analogy: Resource allocation - assign smallest sufficient VM to each workload.
 */
import java.util.*;
public class Problem10_AssignCookies {
    
    public static int findContentChildren(int[] g, int[] s) {
        Arrays.sort(g);
        Arrays.sort(s);
        int i = 0, j = 0;
        while (i < g.length && j < s.length) {
            if (s[j] >= g[i]) i++;
            j++;
        }
        return i;
    }
    
    public static void main(String[] args) {
        System.out.println(findContentChildren(new int[]{1,2,3}, new int[]{1,1}));   // 1
        System.out.println(findContentChildren(new int[]{1,2}, new int[]{1,2,3}));   // 2
        System.out.println(findContentChildren(new int[]{10,9,8,7}, new int[]{5,6,7,8})); // 2
    }
}
