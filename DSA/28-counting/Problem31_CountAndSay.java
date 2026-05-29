/**
 * Problem: Count and Say (LeetCode 38)
 * Approach: Iterative run-length encoding
 * Complexity: O(2^n) worst case for string growth
 * Production Analogy: Run-length encoding in data compression
 */
public class Problem31_CountAndSay {
    public String countAndSay(int n) {
        String s = "1";
        for (int i = 1; i < n; i++) {
            StringBuilder sb = new StringBuilder();
            int count = 1;
            for (int j = 1; j < s.length(); j++) {
                if (s.charAt(j) == s.charAt(j-1)) count++;
                else { sb.append(count).append(s.charAt(j-1)); count = 1; }
            }
            sb.append(count).append(s.charAt(s.length()-1));
            s = sb.toString();
        }
        return s;
    }
    public static void main(String[] args) {
        System.out.println(new Problem31_CountAndSay().countAndSay(5)); // 111221
    }
}
