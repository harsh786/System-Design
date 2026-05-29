import java.util.*;

public class Problem09_ExternalMergeSort {
    // Simulates external merge sort for large files
    static int[][] simulateChunks(int[] data, int chunkSize) {
        int numChunks = (data.length + chunkSize - 1) / chunkSize;
        int[][] chunks = new int[numChunks][];
        for (int i = 0; i < numChunks; i++) {
            int start = i * chunkSize, end = Math.min(start + chunkSize, data.length);
            chunks[i] = Arrays.copyOfRange(data, start, end);
            Arrays.sort(chunks[i]); // Sort each chunk in memory
        }
        return chunks;
    }
    
    static int[] kWayMerge(int[][] chunks) {
        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> a[0] - b[0]);
        int total = 0;
        for (int i = 0; i < chunks.length; i++) { pq.offer(new int[]{chunks[i][0], i, 0}); total += chunks[i].length; }
        int[] result = new int[total];
        int k = 0;
        while (!pq.isEmpty()) {
            int[] top = pq.poll();
            result[k++] = top[0];
            if (top[2] + 1 < chunks[top[1]].length)
                pq.offer(new int[]{chunks[top[1]][top[2] + 1], top[1], top[2] + 1});
        }
        return result;
    }
    
    public static void main(String[] args) {
        int[] data = {9, 3, 7, 1, 8, 2, 6, 4, 5, 0};
        int[][] chunks = simulateChunks(data, 3);
        System.out.println(Arrays.toString(kWayMerge(chunks)));
    }
}
