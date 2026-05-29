import java.util.*;

public class Problem43_StreamMergeKWay {
    // K-way Stream Merge: Merge K sorted streams into one sorted stream.
    
    public List<Integer> mergeKStreams(List<Iterator<Integer>> streams) {
        PriorityQueue<int[]> pq = new PriorityQueue<>((a,b) -> a[0] - b[0]); // [value, streamIndex]
        for (int i = 0; i < streams.size(); i++) {
            if (streams.get(i).hasNext()) pq.offer(new int[]{streams.get(i).next(), i});
        }
        List<Integer> result = new ArrayList<>();
        while (!pq.isEmpty()) {
            int[] top = pq.poll();
            result.add(top[0]);
            if (streams.get(top[1]).hasNext()) pq.offer(new int[]{streams.get(top[1]).next(), top[1]});
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem43_StreamMergeKWay sol = new Problem43_StreamMergeKWay();
        List<Iterator<Integer>> streams = new ArrayList<>();
        streams.add(Arrays.asList(1,4,7,10).iterator());
        streams.add(Arrays.asList(2,5,8,11).iterator());
        streams.add(Arrays.asList(3,6,9,12).iterator());
        System.out.println(sol.mergeKStreams(streams));
    }
}
