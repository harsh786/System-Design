/**
 * Problem 20: Partition Labels
 * 
 * Partition string so each letter appears in at most one part. Maximize partitions.
 * 
 * Approach: Track last occurrence of each char. Expand partition end as we scan.
 * Time: O(n), Space: O(1) (26 chars)
 * 
 * Production Analogy: Like partitioning a distributed transaction log so each
 * entity's events are in exactly one partition - maximizing parallelism.
 */
import java.util.*;

public class Problem20_PartitionLabels {
    public static List<Integer> partitionLabels(String s) {
        int[] last = new int[26];
        for (int i = 0; i < s.length(); i++) last[s.charAt(i) - 'a'] = i;
        List<Integer> result = new ArrayList<>();
        int start = 0, end = 0;
        for (int i = 0; i < s.length(); i++) {
            end = Math.max(end, last[s.charAt(i) - 'a']);
            if (i == end) { result.add(end - start + 1); start = end + 1; }
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(partitionLabels("ababcbacadefegdehijhklij")); // [9,7,8]
        System.out.println(partitionLabels("eccbbbbdec")); // [10]
    }
}
