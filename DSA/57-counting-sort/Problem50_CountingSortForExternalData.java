import java.util.*;

public class Problem50_CountingSortForExternalData {
    // Simulate external sort with counting: chunk data, count locally, merge
    public static int[] externalCountingSort(int[][] chunks, int maxVal) {
        int[] globalCount = new int[maxVal + 1];
        // Process each chunk (simulating external read)
        for (int[] chunk : chunks)
            for (int v : chunk) globalCount[v]++;
        // Reconstruct sorted output
        int total = 0;
        for (int c : globalCount) total += c;
        int[] result = new int[total];
        int idx = 0;
        for (int i = 0; i <= maxVal; i++) while (globalCount[i]-- > 0) result[idx++] = i;
        return result;
    }

    public static void main(String[] args) {
        int[][] chunks = {{5,3,8,1},{9,2,7,4},{6,3,1,8}};
        System.out.println(Arrays.toString(externalCountingSort(chunks, 9)));
    }
}
