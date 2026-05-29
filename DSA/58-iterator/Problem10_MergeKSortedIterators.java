import java.util.*;

public class Problem10_MergeKSortedIterators {
    public static Iterator<Integer> mergeK(List<Iterator<Integer>> iterators) {
        PriorityQueue<int[]> pq = new PriorityQueue<>((a,b)->a[0]-b[0]); // [value, iteratorIdx]
        List<Iterator<Integer>> iters = new ArrayList<>(iterators);
        for (int i = 0; i < iters.size(); i++)
            if (iters.get(i).hasNext()) pq.offer(new int[]{iters.get(i).next(), i});

        return new Iterator<Integer>() {
            public boolean hasNext() { return !pq.isEmpty(); }
            public Integer next() {
                int[] top = pq.poll();
                int idx = top[1];
                if (iters.get(idx).hasNext()) pq.offer(new int[]{iters.get(idx).next(), idx});
                return top[0];
            }
        };
    }

    public static void main(String[] args) {
        List<Iterator<Integer>> iters = Arrays.asList(
            Arrays.asList(1,4,7).iterator(),
            Arrays.asList(2,5,8).iterator(),
            Arrays.asList(3,6,9).iterator());
        Iterator<Integer> merged = mergeK(iters);
        while (merged.hasNext()) System.out.print(merged.next() + " ");
        System.out.println();
    }
}
