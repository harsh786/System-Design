import java.util.*;

public class Problem26_KwayMergeIterator implements Iterator<Integer> {
    PriorityQueue<int[]> pq; // [value, listIdx]
    List<Iterator<Integer>> iters;

    public Problem26_KwayMergeIterator(List<Iterator<Integer>> iterators) {
        iters = iterators;
        pq = new PriorityQueue<>((a,b)->a[0]-b[0]);
        for (int i = 0; i < iters.size(); i++)
            if (iters.get(i).hasNext()) pq.offer(new int[]{iters.get(i).next(), i});
    }

    public boolean hasNext() { return !pq.isEmpty(); }
    public Integer next() {
        int[] top = pq.poll();
        if (iters.get(top[1]).hasNext()) pq.offer(new int[]{iters.get(top[1]).next(), top[1]});
        return top[0];
    }

    public static void main(String[] args) {
        Problem26_KwayMergeIterator it = new Problem26_KwayMergeIterator(Arrays.asList(
            Arrays.asList(1,5,9).iterator(), Arrays.asList(2,6,10).iterator(), Arrays.asList(3,7,11).iterator()));
        while (it.hasNext()) System.out.print(it.next() + " ");
        System.out.println();
    }
}
