import java.util.*;

public class Problem19_MergeSortForLargeFiles {
    // Simulation of external sort with chunk-based processing
    static int CHUNK_SIZE = 4;
    
    static int[] externalSort(int[] data) {
        // Phase 1: Create sorted chunks
        List<int[]> chunks = new ArrayList<>();
        for (int i = 0; i < data.length; i += CHUNK_SIZE) {
            int[] chunk = Arrays.copyOfRange(data, i, Math.min(i + CHUNK_SIZE, data.length));
            Arrays.sort(chunk);
            chunks.add(chunk);
        }
        // Phase 2: K-way merge
        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> a[0] - b[0]);
        for (int i = 0; i < chunks.size(); i++)
            pq.offer(new int[]{chunks.get(i)[0], i, 0});
        int[] result = new int[data.length]; int k = 0;
        while (!pq.isEmpty()) {
            int[] top = pq.poll(); result[k++] = top[0];
            if (top[2] + 1 < chunks.get(top[1]).length)
                pq.offer(new int[]{chunks.get(top[1])[top[2] + 1], top[1], top[2] + 1});
        }
        return result;
    }
    
    public static void main(String[] args) {
        int[] data = {15, 3, 9, 1, 12, 7, 4, 11, 2, 8, 6, 14, 5, 13, 10};
        System.out.println(Arrays.toString(externalSort(data)));
    }
}
