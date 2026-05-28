/**
 * Problem 5: Partition Labels (LeetCode 763)
 *
 * Greedy Choice: Extend current partition to include last occurrence of each char seen.
 * Exchange Argument: Any smaller partition would split a character across partitions.
 *
 * Time: O(n), Space: O(1)
 *
 * Production Analogy: Partitioning log files so that all events of a session stay in same shard.
 */
import java.util.*;
public class Problem05_PartitionLabels {
    
    public static List<Integer> partitionLabels(String s) {
        int[] last = new int[26];
        for (int i = 0; i < s.length(); i++) last[s.charAt(i) - 'a'] = i;
        List<Integer> result = new ArrayList<>();
        int start = 0, end = 0;
        for (int i = 0; i < s.length(); i++) {
            end = Math.max(end, last[s.charAt(i) - 'a']);
            if (i == end) {
                result.add(end - start + 1);
                start = end + 1;
            }
        }
        return result;
    }
    
    public static void main(String[] args) {
        System.out.println(partitionLabels("ababcbacadefegdehijhklij")); // [9,7,8]
        System.out.println(partitionLabels("eccbbbbdec"));               // [10]
        System.out.println(partitionLabels("abc"));                      // [1,1,1]
    }
}
