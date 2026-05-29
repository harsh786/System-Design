import java.util.*;

public class Problem26_MergeSortKSortedIterators {
    static List<Integer> mergeKIterators(List<Iterator<Integer>> iterators) {
        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> a[0] - b[0]);
        for (int i = 0; i < iterators.size(); i++)
            if (iterators.get(i).hasNext()) pq.offer(new int[]{iterators.get(i).next(), i});
        List<Integer> result = new ArrayList<>();
        while (!pq.isEmpty()) {
            int[] top = pq.poll();
            result.add(top[0]);
            if (iterators.get(top[1]).hasNext()) pq.offer(new int[]{iterators.get(top[1]).next(), top[1]});
        }
        return result;
    }
    
    public static void main(String[] args) {
        List<Iterator<Integer>> iters = new ArrayList<>();
        iters.add(Arrays.asList(1, 4, 7).iterator());
        iters.add(Arrays.asList(2, 5, 8).iterator());
        iters.add(Arrays.asList(3, 6, 9).iterator());
        System.out.println(mergeKIterators(iters));
    }
}
