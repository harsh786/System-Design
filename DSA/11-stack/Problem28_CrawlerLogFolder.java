import java.util.*;

/**
 * Problem 28: Crawler Log Folder (LeetCode 1598)
 * 
 * Given folder change logs, find minimum operations to go back to main folder.
 * 
 * Approach: Track depth with counter (or stack). "../" decreases, "./" stays, else increases.
 * 
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Like tracking directory depth in a file system crawler
 * to know how many levels to traverse back to root.
 */
public class Problem28_CrawlerLogFolder {

    public static int minOperations(String[] logs) {
        int depth = 0;
        for (String log : logs) {
            if (log.equals("../")) {
                depth = Math.max(0, depth - 1);
            } else if (!log.equals("./")) {
                depth++;
            }
        }
        return depth;
    }

    public static void main(String[] args) {
        System.out.println(minOperations(new String[]{"d1/","d2/","../","d21/","./"})); // 2
        System.out.println(minOperations(new String[]{"d1/","d2/","./","d3/","../","d31/"})); // 3
        System.out.println(minOperations(new String[]{"d1/","../","../","../"})); // 0
    }
}
