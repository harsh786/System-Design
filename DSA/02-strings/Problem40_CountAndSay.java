import java.util.*;

/**
 * Problem 40: Count and Say (LeetCode 38)
 * 
 * Approach: Iteratively build each term by describing the previous. O(n * m) where m = length of term.
 * 
 * Production Analogy: Like run-length encoding (RLE) used in data compression.
 */
public class Problem40_CountAndSay {

    public static String countAndSay(int n) {
        String s = "1";
        for (int i = 1; i < n; i++) {
            StringBuilder sb = new StringBuilder();
            int count = 1;
            for (int j = 1; j < s.length(); j++) {
                if (s.charAt(j) == s.charAt(j - 1)) count++;
                else { sb.append(count).append(s.charAt(j - 1)); count = 1; }
            }
            sb.append(count).append(s.charAt(s.length() - 1));
            s = sb.toString();
        }
        return s;
    }

    public static void main(String[] args) {
        for (int i = 1; i <= 6; i++) System.out.println(i + ": " + countAndSay(i));
        // 1: "1", 2: "11", 3: "21", 4: "1211", 5: "111221", 6: "312211"
    }
}
