/**
 * Problem 4: Task Scheduler (LeetCode 621)
 *
 * Greedy Choice: Schedule the most frequent task first, fill gaps with others.
 * The minimum time is determined by the most frequent task's count.
 *
 * Time: O(n), Space: O(1) (26 letters)
 *
 * Production Analogy: CPU task scheduling with cooldown between same-type operations
 * (e.g., rate-limited API calls to same endpoint).
 */
public class Problem04_TaskScheduler {
    
    public static int leastInterval(char[] tasks, int n) {
        int[] freq = new int[26];
        for (char t : tasks) freq[t - 'A']++;
        int maxFreq = 0, maxCount = 0;
        for (int f : freq) {
            if (f > maxFreq) { maxFreq = f; maxCount = 1; }
            else if (f == maxFreq) maxCount++;
        }
        int partCount = maxFreq - 1;
        int partLength = n - (maxCount - 1);
        int emptySlots = partCount * partLength;
        int availableTasks = tasks.length - maxFreq * maxCount;
        int idles = Math.max(0, emptySlots - availableTasks);
        return tasks.length + idles;
    }
    
    public static void main(String[] args) {
        System.out.println(leastInterval(new char[]{'A','A','A','B','B','B'}, 2)); // 8
        System.out.println(leastInterval(new char[]{'A','A','A','B','B','B'}, 0)); // 6
        System.out.println(leastInterval(new char[]{'A','A','A','A','A','A','B','C','D','E','F','G'}, 2)); // 16
    }
}
