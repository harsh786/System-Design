import java.util.*;

public class Problem38_KWayExternalFileMerge {
    // Simulate merging k sorted "files" (represented as sorted arrays)
    static int[] kWayFileMerge(int[][] files) {
        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> a[0] - b[0]);
        int total = 0;
        for (int i = 0; i < files.length; i++) { if (files[i].length > 0) { pq.offer(new int[]{files[i][0], i, 0}); total += files[i].length; } }
        int[] result = new int[total]; int k = 0;
        while (!pq.isEmpty()) {
            int[] top = pq.poll(); result[k++] = top[0];
            if (top[2] + 1 < files[top[1]].length) pq.offer(new int[]{files[top[1]][top[2]+1], top[1], top[2]+1});
        }
        return result;
    }
    
    public static void main(String[] args) {
        int[][] files = {{1,10,20},{5,15,25},{3,8,12,30}};
        System.out.println(Arrays.toString(kWayFileMerge(files)));
    }
}
