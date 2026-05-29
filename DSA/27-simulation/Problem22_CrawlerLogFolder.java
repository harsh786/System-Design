/**
 * Problem: Crawler Log Folder (LeetCode 1598)
 * Approach: Track depth counter
 * Complexity: O(n) time, O(1) space
 * Production Analogy: Directory navigation depth tracking in file systems
 */
public class Problem22_CrawlerLogFolder {
    public int minOperations(String[] logs) {
        int depth = 0;
        for (String log : logs) {
            if (log.equals("../")) depth = Math.max(0, depth-1);
            else if (!log.equals("./")) depth++;
        }
        return depth;
    }
    public static void main(String[] args) {
        System.out.println(new Problem22_CrawlerLogFolder().minOperations(
            new String[]{"d1/","d2/","../","d21/","./"})); // 2
    }
}
