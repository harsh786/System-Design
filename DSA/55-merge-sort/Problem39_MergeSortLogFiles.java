import java.util.*;

public class Problem39_MergeSortLogFiles {
    // Merge sorted log entries from multiple sources by timestamp
    static String[][] mergeLogs(String[][] log1, String[][] log2) {
        String[][] result = new String[log1.length + log2.length][2];
        int i = 0, j = 0, k = 0;
        while (i < log1.length && j < log2.length)
            result[k++] = log1[i][0].compareTo(log2[j][0]) <= 0 ? log1[i++] : log2[j++];
        while (i < log1.length) result[k++] = log1[i++];
        while (j < log2.length) result[k++] = log2[j++];
        return Arrays.copyOf(result, k);
    }
    
    public static void main(String[] args) {
        String[][] log1 = {{"2024-01-01T10:00","server1 start"},{"2024-01-01T10:05","server1 ready"}};
        String[][] log2 = {{"2024-01-01T10:02","server2 start"},{"2024-01-01T10:04","server2 ready"}};
        for (String[] entry : mergeLogs(log1, log2)) System.out.println(entry[0] + " " + entry[1]);
    }
}
