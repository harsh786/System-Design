/**
 * Problem: Maximum Number of Balloons (LeetCode 1189)
 * Approach: Count chars, find limiting factor
 * Complexity: O(n) time, O(1) space
 * Production Analogy: Bottleneck analysis in manufacturing/resource planning
 */
public class Problem44_MaximumNumberOfBalloons {
    public int maxNumberOfBalloons(String text) {
        int[] count = new int[26];
        for (char c : text.toCharArray()) count[c-'a']++;
        int min = count['b'-'a'];
        min = Math.min(min, count['a'-'a']);
        min = Math.min(min, count['l'-'a'] / 2);
        min = Math.min(min, count['o'-'a'] / 2);
        min = Math.min(min, count['n'-'a']);
        return min;
    }
    public static void main(String[] args) {
        System.out.println(new Problem44_MaximumNumberOfBalloons().maxNumberOfBalloons("loonbalxballpoon")); // 2
    }
}
